from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Any, Callable, Optional, Union, Awaitable, List

class TransportStatus(Enum):
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    CLOSING = auto()
    ERROR = auto()
    SLEEPING = auto()

class IConnection(ABC):
    """Abstract base class for device connections (Serial, TCP, etc.)."""
    
    @property
    @abstractmethod
    def is_connected(self) -> bool:
        ...
        
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
        """Callback for received data."""
        ...

    @on_received.setter
    @abstractmethod
    def on_received(self, callback: Callable[[bytes], None]) -> None:
        pass
    
    @property
    @abstractmethod
    def on_status_changed(self) -> Callable[[TransportStatus, Optional[str]], None]:
        ...

    @on_status_changed.setter
    @abstractmethod
    def on_status_changed(self, callback: Callable[[TransportStatus, Optional[str]], None]) -> None:
        pass


class ISpooler(ABC):
    """Interface for job spooling and command queuing."""
    
    @abstractmethod
    def start_job(self) -> None:
        """Prepares the spooler for a new job."""
        pass
        
    @abstractmethod
    async def send_command(self, command: str, priority: bool = False) -> List[str]:
        """
        Sends a command. 
        If priority is True, it bypasses the queue (immediate execution).
        Returns the response lines.
        """
        ...
    
    @abstractmethod
    async def stream_gcode(self, gcode: str) -> None:
        """Streams a large G-code block/file."""
        pass
        
    @abstractmethod
    async def cancel(self) -> None:
        """Cancels current operations."""
        pass

    @abstractmethod
    def resume_job(self) -> None:
        """Resumes a job that was paused on error or disconnection."""
        pass


class IDevice(ABC):
    """Abstract base class for a laser device driver."""
    
    @abstractmethod
    async def connect(self) -> None:
        pass
        
    @abstractmethod
    async def disconnect(self) -> None:
        pass
        
    @abstractmethod
    async def home(self) -> None:
        pass
    
    @abstractmethod
    async def move_to(self, x: float, y: float) -> None:
        pass
        
    @abstractmethod
    async def job(self, gcode: str) -> None:
        pass
