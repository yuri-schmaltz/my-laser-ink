import asyncio
import logging
from typing import Optional
from device_api import IDevice, IConnection, SerialConnection, TCPConnection, GCodeSpooler

logger = logging.getLogger(__name__)

class GrblDevice(IDevice):
    def __init__(self, connection: IConnection):
        self.connection = connection
        self.spooler = GCodeSpooler(self.connection)

    @classmethod
    def create_serial(cls, port: str, baudrate: int = 115200) -> "GrblDevice":
        """Factory method to create a serial-connected GRBL device."""
        connection = SerialConnection(port, baudrate)
        return cls(connection)

    @classmethod
    def create_tcp(cls, host: str, port: int = 8888) -> "GrblDevice":
        """Factory method to create a network-connected (TCP) GRBL device."""
        connection = TCPConnection(host, port)
        return cls(connection)
    
    async def connect(self) -> None:
        await self.connection.connect()
        # GRBL wake up?
        await asyncio.sleep(2) # Wait for arduino reset
        await self.connection.send(b"\r\n\r\n")

    async def disconnect(self) -> None:
        await self.connection.disconnect()
        
    async def home(self) -> None:
        await self.spooler.send_command("$H")

    async def move_to(self, x: float, y: float) -> None:
        await self.spooler.send_command(f"G0 X{x} Y{y}")

    async def job(self, gcode: str) -> None:
        self.spooler.start_job()
        await self.spooler.stream_gcode(gcode)
