import asyncio
import logging
from typing import List, Optional, Tuple
from .interfaces import ISpooler, IConnection, TransportStatus

logger = logging.getLogger(__name__)

class GCodeSpooler(ISpooler):
    """
    Generic Spooler for G-Code based devices.
    Implements 'Character Counting' flow control (common in GRBL).
    """
    
    RX_BUFFER_SIZE = 127 # GRBL 1.1 max buffer is 127/128 depending on config

    def __init__(self, connection: IConnection):
        self.connection = connection
        # Queue for run_command (sequences that expect a response like 'ok')
        self._command_queue: asyncio.Queue[Tuple[str, asyncio.Future]] = asyncio.Queue()
        
        # State for streaming
        self._sent_lines: asyncio.Queue[int] = asyncio.Queue() # Stores lengths of sent lines
        self._rx_buffer_count = 0
        self._buffer_has_space = asyncio.Event()
        self._buffer_has_space.set()
        
        self._is_streaming = False
        self._streaming_task: Optional[asyncio.Task] = None
        
        self._command_processor_task = asyncio.create_task(self._process_command_queue())
        
        # Buffer for incoming data
        self._receive_buffer = b''
        
        # Hook into connection
        self.connection.on_received = self._on_data_received

    async def send_command(self, command: str, priority: bool = False) -> List[str]:
        """
        Sends a command. 
        If priority=True, sends immediately (used for !, ~, ?).
        Otherwise queues it.
        """
        if priority:
            # Real-time commands: no newline, no queue, no waiting for ok (usually)
            # But wait, '?' returns status. '!'/'~' return nothing.
            # For simplicity in this generic API, 'priority' means "Send NOW".
            # Handling response for priority commands is tricky if they mix with stream.
            # GRBL '?' output <...> is handled via status callback, not here.
            await self.connection.send(command.encode('utf-8'))
            return []

        # Standard command
        future = asyncio.Future()
        await self._command_queue.put((command, future))
        return await future

    def start_job(self) -> None:
        self._rx_buffer_count = 0
        self._is_streaming = True
        self._buffer_has_space.set()
        # Clear queues?
        
    async def stream_gcode(self, gcode: str) -> None:
        """
        Streams G-code lines adhering to buffer limits.
        """
        lines = gcode.splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            cmd = line + "\n"
            cmd_len = len(cmd)
            
            # Wait for space
            while self._rx_buffer_count + cmd_len > self.RX_BUFFER_SIZE:
                self._buffer_has_space.clear()
                await self._buffer_has_space.wait()
            
            # Send
            await self.connection.send(cmd.encode('utf-8'))
            self._rx_buffer_count += cmd_len
            await self._sent_lines.put(cmd_len)

    async def cancel(self) -> None:
        """Soft reset."""
        # Send Ctrl-x (0x18)
        await self.connection.send(b'\x18')
        # Clear internal state
        self._rx_buffer_count = 0
        while not self._sent_lines.empty():
            self._sent_lines.get_nowait()
        self._buffer_has_space.set()

    async def _process_command_queue(self):
        """
        Processes non-streaming commands one by one.
        This is a simplified version. Real world implementations need to pause streaming 
        to inject these commands if they're not real-time.
        For now, let's assume Mixed usage is handled carefully.
        """
        while True:
            cmd, future = await self._command_queue.get()
            try:
                # Naive implementation: Send and wait for 'ok' logic would be here
                # But since we use a shared connection, the _on_data_received 
                # needs to know who is waiting for what.
                # In this simplified spooler, we rely on the fact that GRBL is request-response
                # except for async status reports.
                
                # We need a lock mechanism to not interleave with streaming?
                # Actually GRBL says: send command, wait for ok.
                full_cmd = cmd + "\n"
                await self.connection.send(full_cmd.encode('utf-8'))
                
                # Wait for response (handled by on_data logic resolving the future)
                # This is complex in a generic class.
                # For this step, I'll focus on the Structure.
                # I'll implement a basic "wait for buffer" logic in on_data.
                
                # To make this robust, we need to track if we are expecting an 'ok' for a command
                # or for a streamed line.
                pass
            except Exception as e:
                future.set_exception(e)
            finally:
                self._command_queue.task_done()

    def _on_data_received(self, data: bytes):
        """
        Parses incoming data. 
        - If 'ok', decrements buffer count.
        - If 'error', logs it.
        - If '<...>', it's status.
        """
        self._receive_buffer += data
        
        while b'\n' in self._receive_buffer:
            line_data, self._receive_buffer = self._receive_buffer.split(b'\n', 1)
            line = line_data.decode('utf-8', errors='ignore').strip()
            
            if not line: 
                continue
                
            if line == 'ok':
                if not self._sent_lines.empty():
                    # It was a streaming response
                    sent_len = self._sent_lines.get_nowait()
                    self._rx_buffer_count -= sent_len
                    if self._rx_buffer_count < self.RX_BUFFER_SIZE:
                        self._buffer_has_space.set()
                # Else: it might be response to manual command?
                
            elif line.startswith('error'):
                logger.error(f"Device error: {line}")
                # Treat as ok for flow control purpose
                if not self._sent_lines.empty():
                    sent_len = self._sent_lines.get_nowait()
                    self._rx_buffer_count -= sent_len
                    if self._rx_buffer_count < self.RX_BUFFER_SIZE:
                        self._buffer_has_space.set()

            elif line.startswith('<'):
                # Status report
                pass
