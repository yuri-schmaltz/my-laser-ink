"""Integration tests for device_api with GRBL drivers."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from packages.device_api.src.device_api.spooler import GCodeSpooler
from packages.device_api.src.device_api.interfaces import (
    IConnection,
    TransportStatus,
)


class SimulatedGRBLConnection(IConnection):
    """Simulates a real GRBL device responding to commands."""

    def __init__(self):
        self._is_connected = False
        self._on_received_cb = None
        self._on_status_changed_cb = None
        self.sent_data = []
        self._simulate_responses = True

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    async def connect(self) -> None:
        self._is_connected = True
        if self._on_status_changed_cb:
            self._on_status_changed_cb(
                TransportStatus.CONNECTED, None
            )
        if self._on_received_cb:
            await asyncio.sleep(0.01)
            self._on_received_cb(b"Grbl 1.1h ['$' for help]\r\n")

    async def disconnect(self) -> None:
        self._is_connected = False
        if self._on_status_changed_cb:
            self._on_status_changed_cb(
                TransportStatus.DISCONNECTED, None
            )

    async def send(self, data: bytes) -> None:
        self.sent_data.append(data)

        if self._simulate_responses and self._on_received_cb:
            await asyncio.sleep(0.005)

            if data == b"?":
                self._on_received_cb(
                    b"<Idle|MPos:0.000,0.000,0.000|FS:0,0>\r\n"
                )
            elif data.startswith(b"G"):
                self._on_received_cb(b"ok\r\n")
            elif data == b"\x18":
                self._on_received_cb(b"ok\r\n")

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


@pytest.fixture
def grbl_connection():
    """Provides a simulated GRBL connection."""
    return SimulatedGRBLConnection()


@pytest.fixture
def grbl_spooler(grbl_connection):
    """Provides a spooler connected to simulated GRBL."""
    return GCodeSpooler(grbl_connection)


@pytest.mark.asyncio
async def test_spooler_with_grbl_integration(grbl_spooler, grbl_connection):
    """Test spooler with simulated GRBL device."""
    await grbl_connection.connect()

    await asyncio.sleep(0.02)

    spooler = grbl_spooler
    spooler.start_job()

    gcode = "G0 X10 Y20\nG1 X30 Y40 F1000\nM5\n"
    await spooler.stream_gcode(gcode)

    assert len(grbl_connection.sent_data) >= 3
    assert b"G0 X10 Y20\n" in grbl_connection.sent_data
    assert b"G1 X30 Y40 F1000\n" in grbl_connection.sent_data
    assert b"M5\n" in grbl_connection.sent_data


@pytest.mark.asyncio
async def test_emergency_stop_via_spooler(grbl_spooler, grbl_connection):
    """Test emergency stop (cancel) functionality."""
    await grbl_connection.connect()
    await asyncio.sleep(0.02)

    spooler = grbl_spooler
    spooler.start_job()

    await spooler.stream_gcode("G0 X10\n")
    await spooler.cancel()

    assert grbl_connection.sent_data[-1] == b"\x18"


@pytest.mark.asyncio
async def test_status_query_via_spooler(grbl_spooler, grbl_connection):
    """Test status query with priority commands."""
    await grbl_connection.connect()
    await asyncio.sleep(0.02)

    await grbl_spooler.send_command("?", priority=True)

    await asyncio.sleep(0.02)

    assert b"?" in grbl_connection.sent_data


@pytest.mark.asyncio
async def test_command_queue_with_responses(grbl_spooler, grbl_connection):
    """Test command queueing with response handling."""
    await grbl_connection.connect()
    await asyncio.sleep(0.02)

    command_task = asyncio.create_task(
        grbl_spooler.send_command("G91 G0 X10")
    )

    result = await asyncio.wait_for(command_task, timeout=1.0)

    assert result == ["ok"]


@pytest.mark.asyncio
async def test_buffer_management_integration(grbl_spooler, grbl_connection):
    """Test that buffer management works with simulated GRBL."""
    await grbl_connection.connect()
    await asyncio.sleep(0.02)

    spooler = grbl_spooler
    spooler.start_job()

    large_commands = "\n".join([f"G0 X{i*10}" for i in range(20)])
    await spooler.stream_gcode(large_commands)

    assert spooler._rx_buffer_count == 0
    assert len(grbl_connection.sent_data) >= 20


@pytest.mark.asyncio
async def test_disconnect_during_operation(grbl_spooler, grbl_connection):
    """Test proper disconnect handling."""
    await grbl_connection.connect()
    await asyncio.sleep(0.02)

    await grbl_connection.disconnect()

    assert not grbl_connection.is_connected
