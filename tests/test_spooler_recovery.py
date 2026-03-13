"""Tests for GCodeSpooler recovery logic."""

import asyncio
import pytest
from packages.device_api.src.device_api.spooler import GCodeSpooler
from packages.device_api.src.device_api.interfaces import (
    IConnection,
    TransportStatus,
)

class MockConnection(IConnection):
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
            self._on_status_changed_cb(TransportStatus.CONNECTED, None)

    async def disconnect(self) -> None:
        self._is_connected = False
        if self._on_status_changed_cb:
            self._on_status_changed_cb(TransportStatus.DISCONNECTED, None)

    async def send(self, data: bytes) -> None:
        if not self._is_connected:
            raise ConnectionError("Mock connection lost!")
        self.sent_data.append(data)

    @property
    def on_received(self): return self._on_received_cb
    @on_received.setter
    def on_received(self, cb): self._on_received_cb = cb

    @property
    def on_status_changed(self): return self._on_status_changed_cb
    @on_status_changed.setter
    def on_status_changed(self, cb): self._on_status_changed_cb = cb

@pytest.mark.asyncio
async def test_spooler_recovery_flow():
    conn = MockConnection()
    await conn.connect()
    spooler = GCodeSpooler(conn)
    spooler.start_job()

    gcode = "G0 X1\nG0 X2\nG0 X3\n"
    
    # Run streaming in background
    stream_task = asyncio.create_task(spooler.stream_gcode(gcode))
    await asyncio.sleep(0.01)

    # Simulate disconnect during stream
    await conn.disconnect()
    # Spooler should detect it via callback
    spooler._on_connection_status_changed(TransportStatus.DISCONNECTED, "Link lost")

    assert spooler._is_paused_on_error is True
    assert spooler._is_streaming is False
    
    # Sent data should contain at least the first command (depending on timing)
    # but the task should be waiting.
    assert not stream_task.done()

    # Reconnect
    await conn.connect()
    spooler.resume_job()

    assert spooler._is_paused_on_error is False
    assert spooler._is_streaming is True

    # Finish job by acknowledging sent commands
    initial_sent_count = len(conn.sent_data)
    for _ in range(initial_sent_count):
        spooler._on_data_received(b"ok\n")
    
    # Let it finish
    await asyncio.wait_for(stream_task, timeout=1.0)
    
    # Check that all commands were eventually sent
    # We expect 3 total commands
    assert len(conn.sent_data) == 3
    assert conn.sent_data[0] == b"G0 X1\n"
    assert conn.sent_data[1] == b"G0 X2\n"
    assert conn.sent_data[2] == b"G0 X3\n"
