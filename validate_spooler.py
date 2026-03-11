#!/usr/bin/env python3
"""
Manual validation script for the GCodeSpooler implementation.
This script tests the spooler without requiring external dependencies like pytest.
"""

import asyncio
import sys
from pathlib import Path
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Callable, Optional, List
from collections import deque
import logging

logger = logging.getLogger(__name__)


class TransportStatus(Enum):
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    CLOSING = auto()
    ERROR = auto()
    SLEEPING = auto()


class IConnection(ABC):
    """Abstract base class for device connections."""

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        pass

    @abstractmethod
    async def connect(self) -> None:
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        pass

    @abstractmethod
    async def send(self, data: bytes) -> None:
        pass

    @property
    @abstractmethod
    def on_received(self) -> Callable[[bytes], None]:
        pass

    @on_received.setter
    @abstractmethod
    def on_received(self, callback: Callable[[bytes], None]) -> None:
        pass

    @property
    @abstractmethod
    def on_status_changed(
        self,
    ) -> Callable[[TransportStatus, Optional[str]], None]:
        pass

    @on_status_changed.setter
    @abstractmethod
    def on_status_changed(
        self, callback: Callable[[TransportStatus, Optional[str]], None]
    ) -> None:
        pass


class GCodeSpooler:
    """
    Generic Spooler for G-Code based devices.
    Implements 'Character Counting' flow control (common in GRBL).
    """

    RX_BUFFER_SIZE = 127

    def __init__(self, connection: IConnection):
        self.connection = connection
        self._command_queue = asyncio.Queue()
        self._sent_lines = asyncio.Queue()
        self._rx_buffer_count = 0
        self._buffer_has_space = asyncio.Event()
        self._buffer_has_space.set()
        self._is_streaming = False
        self._streaming_task = None
        self._command_processor_task = asyncio.create_task(
            self._process_command_queue()
        )
        self._receive_buffer = b""
        self._pending_responses = deque()
        self._response_lock = asyncio.Lock()
        self.connection.on_received = self._on_data_received

    async def send_command(self, command: str, priority: bool = False):
        """Send a command, queueing if needed."""
        if priority:
            await self.connection.send(command.encode("utf-8"))
            return []

        future = asyncio.Future()
        await self._command_queue.put((command, future))
        return await future

    def start_job(self) -> None:
        self._rx_buffer_count = 0
        self._is_streaming = True
        self._buffer_has_space.set()

    async def stream_gcode(self, gcode: str) -> None:
        """Stream G-code lines adhering to buffer limits."""
        lines = gcode.splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue

            cmd = line + "\n"
            cmd_len = len(cmd)

            while self._rx_buffer_count + cmd_len > self.RX_BUFFER_SIZE:
                self._buffer_has_space.clear()
                await self._buffer_has_space.wait()

            await self.connection.send(cmd.encode("utf-8"))
            self._rx_buffer_count += cmd_len
            await self._sent_lines.put(cmd_len)

    async def cancel(self) -> None:
        """Soft reset."""
        await self.connection.send(b"\x18")
        self._rx_buffer_count = 0
        while not self._sent_lines.empty():
            self._sent_lines.get_nowait()
        self._buffer_has_space.set()

    async def _process_command_queue(self):
        """Process queued commands."""
        while True:
            cmd, future = await self._command_queue.get()
            try:
                async with self._response_lock:
                    response_lines = []
                    self._pending_responses.append((future, response_lines))

                    full_cmd = cmd + "\n"
                    await self.connection.send(full_cmd.encode("utf-8"))

                    while not future.done():
                        await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                if not future.done():
                    future.cancel()
            except Exception as e:
                if not future.done():
                    future.set_exception(e)
            finally:
                self._command_queue.task_done()

    def _on_data_received(self, data: bytes):
        """Parse incoming data."""
        self._receive_buffer += data

        while b"\n" in self._receive_buffer:
            line_data, self._receive_buffer = (
                self._receive_buffer.split(b"\n", 1)
            )
            line = line_data.decode("utf-8", errors="ignore").strip()

            if not line:
                continue

            if line == "ok":
                self._handle_ok_response()
            elif line.startswith("error"):
                self._handle_error_response(line)
            elif line.startswith("<"):
                self._handle_status_report(line)

    def _handle_ok_response(self) -> None:
        """Handle OK response."""
        if self._pending_responses and not self._pending_responses[0][0].done():
            future, response_lines = self._pending_responses.popleft()
            response_lines.append("ok")
            if not future.done():
                future.set_result(response_lines)
        elif not self._sent_lines.empty():
            sent_len = self._sent_lines.get_nowait()
            self._rx_buffer_count -= sent_len
            if self._rx_buffer_count < self.RX_BUFFER_SIZE:
                self._buffer_has_space.set()

    def _handle_error_response(self, line: str) -> None:
        """Handle error response."""
        logger.error(f"Device error: {line}")
        if self._pending_responses and not self._pending_responses[0][0].done():
            future, response_lines = self._pending_responses.popleft()
            response_lines.append(line)
            if not future.done():
                future.set_exception(RuntimeError(line))
        elif not self._sent_lines.empty():
            sent_len = self._sent_lines.get_nowait()
            self._rx_buffer_count -= sent_len
            if self._rx_buffer_count < self.RX_BUFFER_SIZE:
                self._buffer_has_space.set()

    def _handle_status_report(self, line: str) -> None:
        """Handle status report."""
        pass
    """Mock connection for validation."""

    def __init__(self):
        self._is_connected = False
        self._on_received_cb = None
        self._on_status_changed_cb = None
        self.sent_data = []

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    async def connect(self) -> None:
        self._is_connected = True

    async def disconnect(self) -> None:
        self._is_connected = False

    async def send(self, data: bytes) -> None:
        self.sent_data.append(data)

    @property
    def on_received(self):
        return self._on_received_cb

    @on_received.setter
    def on_received(self, callback):
        self._on_received_cb = callback

    @property
    def on_status_changed(self):
        return self._on_status_changed_cb

    @on_status_changed.setter
    def on_status_changed(self, callback):
        self._on_status_changed_cb = callback


async def test_basic_streaming():
    """Test basic G-code streaming."""
    print("Testing basic streaming...", end=" ")
    connection = MockConnection()
    spooler = GCodeSpooler(connection)
    spooler.start_job()

    gcode = "G0 X10 Y20\nG1 X30 Y40 F1000\n"
    await spooler.stream_gcode(gcode)

    assert len(connection.sent_data) == 2
    assert connection.sent_data[0] == b"G0 X10 Y20\n"
    print("✓ PASS")


async def test_empty_lines_skipped():
    """Test that empty lines are skipped."""
    print("Testing empty line skipping...", end=" ")
    connection = MockConnection()
    spooler = GCodeSpooler(connection)
    spooler.start_job()

    gcode = "G0 X10\n\n  \nG1 X20\n"
    await spooler.stream_gcode(gcode)

    assert len(connection.sent_data) == 2
    print("✓ PASS")


async def test_priority_commands():
    """Test priority command bypass."""
    print("Testing priority commands...", end=" ")
    connection = MockConnection()
    spooler = GCodeSpooler(connection)

    await spooler.send_command("?", priority=True)

    assert len(connection.sent_data) == 1
    assert connection.sent_data[0] == b"?"
    print("✓ PASS")


async def test_command_response():
    """Test command response handling."""
    print("Testing command response handling...", end=" ")
    connection = MockConnection()
    spooler = GCodeSpooler(connection)

    task = asyncio.create_task(spooler.send_command("G0 X10"))
    await asyncio.sleep(0.01)

    spooler._on_data_received(b"ok\n")
    response = await asyncio.wait_for(task, timeout=1.0)

    assert response == ["ok"]
    print("✓ PASS")


async def test_error_handling():
    """Test error response handling."""
    print("Testing error handling...", end=" ")
    connection = MockConnection()
    spooler = GCodeSpooler(connection)

    task = asyncio.create_task(spooler.send_command("G0 X10"))
    await asyncio.sleep(0.01)

    spooler._on_data_received(b"error: Bad axis\n")

    try:
        await asyncio.wait_for(task, timeout=1.0)
        assert False, "Should have raised RuntimeError"
    except RuntimeError:
        print("✓ PASS")


async def test_buffer_control():
    """Test buffer flow control."""
    print("Testing buffer control...", end=" ")
    connection = MockConnection()
    spooler = GCodeSpooler(connection)
    spooler.start_job()

    gcode = "G0 X10\nG1 X20\nG2 X30\n"
    await spooler.stream_gcode(gcode)

    assert spooler._rx_buffer_count > 0

    for _ in range(3):
        spooler._on_data_received(b"ok\n")

    assert spooler._rx_buffer_count == 0
    print("✓ PASS")


async def test_cancel():
    """Test cancel/soft reset."""
    print("Testing cancel functionality...", end=" ")
    connection = MockConnection()
    spooler = GCodeSpooler(connection)
    spooler.start_job()

    await spooler.stream_gcode("G0 X10\n")

    assert spooler._rx_buffer_count > 0

    await spooler.cancel()

    assert spooler._rx_buffer_count == 0
    assert connection.sent_data[-1] == b"\x18"
    print("✓ PASS")


async def test_status_report():
    """Test status report handling."""
    print("Testing status report...", end=" ")
    connection = MockConnection()
    spooler = GCodeSpooler(connection)

    spooler._on_data_received(b"<Idle|MPos:0.000,0.000,0.000>\n")

    assert len(connection.sent_data) == 0
    print("✓ PASS")


async def main():
    """Run all validation tests."""
    print("\n" + "=" * 60)
    print("GCodeSpooler Validation Tests")
    print("=" * 60 + "\n")

    tests = [
        test_basic_streaming,
        test_empty_lines_skipped,
        test_priority_commands,
        test_command_response,
        test_error_handling,
        test_buffer_control,
        test_cancel,
        test_status_report,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            await test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"✗ FAIL: {e}")

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60 + "\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
