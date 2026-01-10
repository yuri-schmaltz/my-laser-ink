import asyncio
import logging
import sys
import os

import sys
from unittest.mock import MagicMock

# Mock serial dependencies before import
sys.modules["serial"] = MagicMock()
sys.modules["serial_asyncio"] = MagicMock()

# Add packages to path
sys.path.append(os.path.abspath("packages/device_api/src"))
sys.path.append(os.path.abspath("packages/drivers/grbl/src"))

from device_api import IConnection, TransportStatus, GCodeSpooler
from grbl import GrblDevice

# Mock Connection
class MockConnection(IConnection):
    def __init__(self):
        self._connected = False
        self._on_received = None
        self._on_status_changed = None
        self.sent_data = []

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def on_received(self) -> any:
        return self._on_received

    @on_received.setter
    def on_received(self, cb):
        self._on_received = cb
    
    @property
    def on_status_changed(self) -> any:
        return self._on_status_changed

    @on_status_changed.setter
    def on_status_changed(self, cb):
        self._on_status_changed = cb

    async def connect(self):
        self._connected = True
        if self._on_status_changed:
            self._on_status_changed(TransportStatus.CONNECTED, "Mock Connected")
            
    async def disconnect(self):
        self._connected = False
        if self._on_status_changed:
            self._on_status_changed(TransportStatus.DISCONNECTED, "Mock Disconnected")

    async def send(self, data: bytes):
        print(f"MOCK TX: {data}")
        self.sent_data.append(data)
        # Simulate 'ok' response for G-code lines (ending in \n)
        if b'\n' in data:
            # Short delay to simulate processing
            await asyncio.sleep(0.01)
            if self._on_received:
                print("MOCK RX: ok\\n")
                self._on_received(b"ok\n")


async def test_streaming():
    logging.basicConfig(level=logging.INFO)
    print("--- Starting Streaming Test ---")
    
    mock_conn = MockConnection()
    spooler = GCodeSpooler(mock_conn)
    spooler.RX_BUFFER_SIZE = 50 # Small buffer to force flow control logic
    
    await mock_conn.connect()
    spooler.start_job()
    
    # Generate G-Code larger than buffer
    # Each line is "G1 X... Y...\n" ~ 15-20 bytes.
    # 5 lines = ~100 bytes > 50 bytes buffer.
    gcode = ""
    for i in range(10):
        gcode += f"G1 X{i} Y{i}\n"
        
    print(f"Streaming {len(gcode)} bytes...")
    await spooler.stream_gcode(gcode)
    
    print("Streaming finished.")
    await asyncio.sleep(0.5) # Wait for final ok
    
    assert len(mock_conn.sent_data) == 10
    print("--- Test Passed: All lines sent ---")

if __name__ == "__main__":
    asyncio.run(test_streaming())
