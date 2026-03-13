import asyncio
import sys
import os

# Ensure we can import from the current directory and packages
sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), "packages/device_api/src"))

from device_api.spooler import GCodeSpooler
from device_api.interfaces import IConnection, TransportStatus

class MockConnection(IConnection):
    def __init__(self):
        self._is_connected = False
        self._on_received_cb = None
        self._on_status_changed_cb = None
        self.sent_data = []

    @property
    def is_connected(self) -> bool: return self._is_connected

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
        if hasattr(self, 'on_sent_event') and self.on_sent_event:
            self.on_sent_event.set()

    @property
    def on_received(self): return self._on_received_cb
    @on_received.setter
    def on_received(self, cb): self._on_received_cb = cb

    @property
    def on_status_changed(self): return self._on_status_changed_cb
    @on_status_changed.setter
    def on_status_changed(self, cb): self._on_status_changed_cb = cb

async def test_recovery():
    print("Starting recovery test...")
    conn = MockConnection()
    await conn.connect()
    spooler = GCodeSpooler(conn)
    spooler.start_job()

    gcode = "\n".join([f"G1 X{i} F1000" for i in range(100)])
    
    conn.on_sent_event = asyncio.Event()
    conn.on_sent_event.clear()
    
    # Run streaming in background
    stream_task = asyncio.create_task(spooler.stream_gcode(gcode))
    # Wait until at least one line is sent
    await asyncio.wait_for(conn.on_sent_event.wait(), timeout=1.0)

    print("Simulating disconnect...")
    await conn.disconnect()
    spooler._on_connection_status_changed(TransportStatus.DISCONNECTED, "Link lost")

    print(f"Task status: done={stream_task.done()}")
    if stream_task.done():
        try:
            stream_task.result()
        except Exception as e:
            print(f"Task failed with: {e}")
    
    assert not stream_task.done()
    print("Spooler paused correctly.")

    print("Reconnecting and resuming...")
    await conn.connect()
    spooler.resume_job()

    assert spooler._is_paused_on_error is False
    assert spooler._is_streaming is True

    # Finish job by acknowledging sent commands
    # We need to send 'ok' for every command sent to clear the buffer
    print(f"Acking {len(conn.sent_data)} sent commands...")
    while conn.sent_data:
        spooler._on_data_received(b"ok\n")
        await asyncio.sleep(0) # yield to let spooler send more if it wants
    
    # The spooler might send more lines after some are acked
    # Let's keep acking until it's done
    async def auto_ack():
        last_count = 0
        while not stream_task.done():
            if len(conn.sent_data) > last_count:
                for _ in range(len(conn.sent_data) - last_count):
                    spooler._on_data_received(b"ok\n")
                last_count = len(conn.sent_data)
            await asyncio.sleep(0.01)

    ack_task = asyncio.create_task(auto_ack())
    
    await asyncio.wait_for(stream_task, timeout=5.0)
    ack_task.cancel()
    
    assert len(conn.sent_data) == 100
    print("Test PASSED!")

if __name__ == "__main__":
    asyncio.run(test_recovery())
