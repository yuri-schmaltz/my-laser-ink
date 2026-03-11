"""Tests for the GCodeSpooler implementation."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from packages.device_api.src.device_api.spooler import GCodeSpooler
from packages.device_api.src.device_api.interfaces import (
    IConnection,
    TransportStatus,
)


class MockConnection(IConnection):
    """A mock connection for testing."""

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
        if self._on_status_changed_cb:
            self._on_status_changed_cb(
                TransportStatus.CONNECTED, None
            )

    async def disconnect(self) -> None:
        self._is_connected = False
        if self._on_status_changed_cb:
            self._on_status_changed_cb(
                TransportStatus.DISCONNECTED, None
            )

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


@pytest.fixture
def mock_connection():
    """Provides a mock connection for testing."""
    return MockConnection()


@pytest.fixture
def spooler(mock_connection):
    """Provides a GCodeSpooler with a mock connection."""
    return GCodeSpooler(mock_connection)


@pytest.mark.asyncio
async def test_spooler_initialization(spooler):
    """Test that spooler initializes with correct state."""
    assert spooler.connection is not None
    assert spooler._rx_buffer_count == 0
    assert spooler._is_streaming is False
    assert len(spooler.sent_data) == 0


@pytest.mark.asyncio
async def test_stream_gcode_basic(spooler, mock_connection):
    """Test basic G-code streaming."""
    gcode = "G0 X10 Y20\nG1 X30 Y40 F1000\n"
    spooler.start_job()

    await spooler.stream_gcode(gcode)

    assert len(mock_connection.sent_data) == 2
    assert mock_connection.sent_data[0] == b"G0 X10 Y20\n"
    assert mock_connection.sent_data[1] == b"G1 X30 Y40 F1000\n"


@pytest.mark.asyncio
async def test_stream_gcode_skips_empty_lines(spooler, mock_connection):
    """Test that empty lines are skipped."""
    gcode = "G0 X10\n\n  \nG1 X20\n"
    spooler.start_job()

    await spooler.stream_gcode(gcode)

    assert len(mock_connection.sent_data) == 2
    assert mock_connection.sent_data[0] == b"G0 X10\n"
    assert mock_connection.sent_data[1] == b"G1 X20\n"


@pytest.mark.asyncio
async def test_send_command_queues_standard_command(spooler, mock_connection):
    """Test that standard commands are queued."""
    task = asyncio.create_task(spooler.send_command("G0 X10"))
    await asyncio.sleep(0.01)

    assert len(mock_connection.sent_data) == 1
    assert mock_connection.sent_data[0] == b"G0 X10\n"


@pytest.mark.asyncio
async def test_send_command_priority_bypasses_queue(spooler, mock_connection):
    """Test that priority commands bypass the normal queue."""
    await spooler.send_command("?", priority=True)

    assert len(mock_connection.sent_data) == 1
    assert mock_connection.sent_data[0] == b"?"


@pytest.mark.asyncio
async def test_command_response_resolution(spooler, mock_connection):
    """Test that futures are resolved when 'ok' is received."""
    command_task = asyncio.create_task(spooler.send_command("G0 X10"))
    await asyncio.sleep(0.01)

    spooler._on_data_received(b"ok\n")
    response = await asyncio.wait_for(command_task, timeout=1.0)

    assert response == ["ok"]


@pytest.mark.asyncio
async def test_command_error_response(spooler, mock_connection):
    """Test that errors are handled properly."""
    command_task = asyncio.create_task(spooler.send_command("G0 X10"))
    await asyncio.sleep(0.01)

    spooler._on_data_received(b"error: Bad axis\n")

    with pytest.raises(RuntimeError):
        await asyncio.wait_for(command_task, timeout=1.0)


@pytest.mark.asyncio
async def test_buffer_flow_control(spooler, mock_connection):
    """Test buffer fill and space notification."""
    spooler.start_job()

    large_gcode = "\n".join([f"G0 X{i}" for i in range(30)])
    stream_task = asyncio.create_task(spooler.stream_gcode(large_gcode))
    await asyncio.sleep(0.05)

    assert spooler._rx_buffer_count > 0

    spooler._on_data_received(b"ok\n" * 5)

    await asyncio.wait_for(stream_task, timeout=2.0)

    assert len(mock_connection.sent_data) > 0


@pytest.mark.asyncio
async def test_cancel_clears_state(spooler, mock_connection):
    """Test that cancel clears internal state."""
    spooler.start_job()
    await spooler.stream_gcode("G0 X10\nG1 X20\n")

    assert spooler._rx_buffer_count > 0

    await spooler.cancel()

    assert spooler._rx_buffer_count == 0
    assert mock_connection.sent_data[-1] == b"\x18"


@pytest.mark.asyncio
async def test_status_report_handling(spooler, mock_connection):
    """Test that status reports are handled correctly."""
    spooler._on_data_received(b"<Idle|MPos:0.000,0.000,0.000>\n")

    assert len(mock_connection.sent_data) == 0


@pytest.mark.asyncio
async def test_multiple_responses_in_single_receive(spooler, mock_connection):
    """Test handling multiple responses in a single receive event."""
    command_task = asyncio.create_task(spooler.send_command("G0 X10"))
    await asyncio.sleep(0.01)

    spooler._on_data_received(b"ok\n")
    response = await asyncio.wait_for(command_task, timeout=1.0)

    assert response == ["ok"]


@pytest.mark.asyncio
async def test_streaming_with_ok_responses(spooler, mock_connection):
    """Test that streaming correctly processes 'ok' responses."""
    spooler.start_job()
    gcode = "G0 X10\nG1 X20\n"

    stream_task = asyncio.create_task(spooler.stream_gcode(gcode))
    await asyncio.sleep(0.02)

    for i, data in enumerate(mock_connection.sent_data):
        spooler._on_data_received(b"ok\n")

    await asyncio.wait_for(stream_task, timeout=1.0)
    assert spooler._rx_buffer_count == 0
