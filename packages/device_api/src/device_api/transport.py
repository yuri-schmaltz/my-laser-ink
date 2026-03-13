import asyncio
import logging
import serial_asyncio
from typing import Optional, Callable
from .interfaces import IConnection, TransportStatus

logger = logging.getLogger(__name__)

class SerialConnection(IConnection):
    def __init__(self, port: str, baudrate: int):
        self.port = port
        self.baudrate = baudrate
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._running = False
        self._receive_task: Optional[asyncio.Task] = None
        
        self._on_received_cb: Optional[Callable[[bytes], None]] = None
        self._on_status_changed_cb: Optional[Callable[[TransportStatus, Optional[str]], None]] = None

    @property
    def is_connected(self) -> bool:
        return self._writer is not None and self._running

    @property
    def on_received(self) -> Callable[[bytes], None]:
        return self._on_received_cb

    @on_received.setter
    def on_received(self, callback: Callable[[bytes], None]) -> None:
        self._on_received_cb = callback

    @property
    def on_status_changed(self) -> Callable[[TransportStatus, Optional[str]], None]:
        return self._on_status_changed_cb

    @on_status_changed.setter
    def on_status_changed(self, callback: Callable[[TransportStatus, Optional[str]], None]) -> None:
        self._on_status_changed_cb = callback

    async def connect(self) -> None:
        self._notify_status(TransportStatus.CONNECTING)
        try:
            self._reader, self._writer = await serial_asyncio.open_serial_connection(
                url=self.port, baudrate=self.baudrate
            )
            self._running = True
            self._notify_status(TransportStatus.CONNECTED)
            self._receive_task = asyncio.create_task(self._receive_loop())
        except Exception as e:
            logger.error(f"Serial connection failed: {e}")
            self._notify_status(TransportStatus.ERROR, str(e))
            raise

    async def disconnect(self) -> None:
        self._notify_status(TransportStatus.CLOSING)
        self._running = False
        
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None

        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
            
        self._reader = None
        self._notify_status(TransportStatus.DISCONNECTED)

    async def send(self, data: bytes) -> None:
        if not self._writer:
            raise ConnectionError("Not connected")
        self._writer.write(data)
        await self._writer.drain()

    async def _receive_loop(self) -> None:
        while self._running and self._reader:
            try:
                data = await self._reader.read(1024)
                if data:
                    if self._on_received_cb:
                        self._on_received_cb(data)
                else:
                    # EOF
                    break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Receive loop error: {e}")
                self._notify_status(TransportStatus.ERROR, str(e))
                break
        
        if self._running:
            # If we exited loop unexpectedly but still think we are running
            await self.disconnect()

    def _notify_status(self, status: TransportStatus, message: Optional[str] = None):
        if self._on_status_changed_cb:
            self._on_status_changed_cb(status, message)


class TCPConnection(IConnection):
    """Connection implementation for TCP/IP (WiFi/Ethernet)."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._running = False
        self._receive_task: Optional[asyncio.Task] = None

        self._on_received_cb: Optional[Callable[[bytes], None]] = None
        self._on_status_changed_cb: Optional[
            Callable[[TransportStatus, Optional[str]], None]
        ] = None

    @property
    def is_connected(self) -> bool:
        return self._writer is not None and self._running

    @property
    def on_received(self) -> Callable[[bytes], None]:
        return self._on_received_cb

    @on_received.setter
    def on_received(self, callback: Callable[[bytes], None]) -> None:
        self._on_received_cb = callback

    @property
    def on_status_changed(
        self,
    ) -> Callable[[TransportStatus, Optional[str]], None]:
        return self._on_status_changed_cb

    @on_status_changed.setter
    def on_status_changed(
        self, callback: Callable[[TransportStatus, Optional[str]], None]
    ) -> None:
        self._on_status_changed_cb = callback

    async def connect(self) -> None:
        self._notify_status(TransportStatus.CONNECTING)
        try:
            self._reader, self._writer = await asyncio.open_connection(
                host=self.host, port=self.port
            )
            self._running = True
            self._notify_status(TransportStatus.CONNECTED)
            self._receive_task = asyncio.create_task(self._receive_loop())
        except Exception as e:
            logger.error(f"TCP connection failed to {self.host}:{self.port}: {e}")
            self._notify_status(TransportStatus.ERROR, str(e))
            raise

    async def disconnect(self) -> None:
        self._notify_status(TransportStatus.CLOSING)
        self._running = False

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None

        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None

        self._reader = None
        self._notify_status(TransportStatus.DISCONNECTED)

    async def send(self, data: bytes) -> None:
        if not self._writer:
            raise ConnectionError("Not connected")
        self._writer.write(data)
        await self._writer.drain()

    async def _receive_loop(self) -> None:
        while self._running and self._reader:
            try:
                data = await self._reader.read(1024)
                if data:
                    if self._on_received_cb:
                        self._on_received_cb(data)
                else:
                    # EOF (server closed connection)
                    logger.info("TCP Connection closed by remote host")
                    break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"TCP Receive loop error: {e}")
                self._notify_status(TransportStatus.ERROR, str(e))
                break

        if self._running:
            await self.disconnect()

    def _notify_status(
        self, status: TransportStatus, message: Optional[str] = None
    ):
        if self._on_status_changed_cb:
            self._on_status_changed_cb(status, message)
