import asyncio
import logging
from typing import List, Optional, Tuple, Deque
from collections import deque
from .interfaces import ISpooler, IConnection, TransportStatus

logger = logging.getLogger(__name__)

class GCodeSpooler(ISpooler):
    """
    Generic Spooler for G-Code based devices.
    Implements 'Character Counting' flow control (common in GRBL).
    """
    
    RX_BUFFER_SIZE = 127

    def __init__(self, connection: IConnection):
        self.connection = connection
        self._command_queue: asyncio.Queue[Tuple[str, asyncio.Future]] = (
            asyncio.Queue()
        )
        
        self._sent_lines: asyncio.Queue[int] = asyncio.Queue()
        self._rx_buffer_count = 0
        self._buffer_has_space = asyncio.Event()
        self._buffer_has_space.set()
        
        self._is_streaming = False
        self._is_paused_on_error = False
        self._streaming_task: Optional[asyncio.Task] = None
        
        self._command_processor_task = asyncio.create_task(
            self._process_command_queue()
        )
        
        self._receive_buffer = b''
        
        self._pending_responses: Deque[Tuple[asyncio.Future, List[str]]] = (
            deque()
        )
        self._response_lock = asyncio.Lock()
        
        self.connection.on_received = self._on_data_received
        self.connection.on_status_changed = self._on_connection_status_changed

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
            logger.debug(f"Streaming line: {line.strip()} (len: {cmd_len})")
            
            # Wait for space or pause
            await self._wait_for_space(cmd_len)
            
            # Re-check if we are still streaming/not paused after wait
            if not self._is_streaming and not self._is_paused_on_error:
                logger.debug("Breaking stream loop: not streaming and not paused")
                break

            # Send
            await self.connection.send(cmd.encode('utf-8'))
            self._rx_buffer_count += cmd_len
            await self._sent_lines.put(cmd_len)

            # Check if we should pause immediately (race condition mitigation)
            if self._is_paused_on_error:
                logger.debug("Pausing stream_gcode immediately after sending command")
                await self._wait_for_space(0)

    async def cancel(self) -> None:
        """Soft reset."""
        # Send Ctrl-x (0x18)
        try:
            await self.connection.send(b'\x18')
        except Exception:
            logger.warning("Failed to send cancel command (not connected?)")
        
        # Clear internal state
        self._rx_buffer_count = 0
        while not self._sent_lines.empty():
            self._sent_lines.get_nowait()
        self._buffer_has_space.set()
        self._is_paused_on_error = False
        self._is_streaming = False

    def resume_job(self) -> None:
        """Resumes a job that was paused on error or disconnection."""
        if not self._is_paused_on_error:
            logger.warning("resume_job called but not in paused-on-error state.")
            return
        
        if not self.connection.is_connected:
            logger.error("Cannot resume job: not connected.")
            return

        logger.info("Resuming job.")
        self._is_paused_on_error = False
        self._is_streaming = True
        self._buffer_has_space.set()

    async def _wait_for_space(self, cmd_len: int) -> None:
        """Waits until there is enough space in the RX buffer AND we are not paused on error."""
        while (self._rx_buffer_count + cmd_len > self.RX_BUFFER_SIZE or self._is_paused_on_error) and (self._is_streaming or self._is_paused_on_error):
            self._buffer_has_space.clear()
            await self._buffer_has_space.wait()

    async def _process_command_queue(self):
        """
        Processes non-streaming commands sequentially.
        Sent commands are tracked and responses resolve futures.
        """
        while True:
            cmd, future = await self._command_queue.get()
            try:
                async with self._response_lock:
                    response_lines: List[str] = []
                    self._pending_responses.append((future, response_lines))
                    
                    full_cmd = cmd + "\n"
                    await self.connection.send(full_cmd.encode('utf-8'))
                    
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
        """
        Parses incoming data and updates buffer/command responses.
        Handles 'ok', 'error', and status reports.
        """
        self._receive_buffer += data
        
        while b'\n' in self._receive_buffer:
            line_data, self._receive_buffer = (
                self._receive_buffer.split(b'\n', 1)
            )
            line = line_data.decode('utf-8', errors='ignore').strip()
            
            if not line:
                continue
            
            if line == 'ok':
                self._handle_ok_response()
            elif line.startswith('error'):
                self._handle_error_response(line)
            elif line.startswith('<'):
                self._handle_status_report(line)
    
    def _handle_ok_response(self) -> None:
        """
        Handles 'ok' response: either for streaming or command.
        """
        if self._pending_responses and not self._pending_responses[0][0].done():
            future, response_lines = self._pending_responses.popleft()
            response_lines.append('ok')
            if not future.done():
                future.set_result(response_lines)
        elif not self._sent_lines.empty():
            sent_len = self._sent_lines.get_nowait()
            self._rx_buffer_count -= sent_len
            if self._rx_buffer_count < self.RX_BUFFER_SIZE:
                self._buffer_has_space.set()
    
    def _handle_error_response(self, line: str) -> None:
        """
        Handles error response: logs and either resolves future or updates buffer.
        """
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
        """
        Handles status report (format: <Idle|Run|Hold|Door|Home|...|...>).
        Can be emitted asynchronously and should not consume a response.
        """
        pass

    def _on_connection_status_changed(
        self, status: TransportStatus, message: Optional[str] = None
    ) -> None:
        """
        Handles connection status changes.
        """
        if status == TransportStatus.ERROR or status == TransportStatus.DISCONNECTED:
            if self._is_streaming:
                logger.error(f"Connection lost while streaming: {message}")
                self._is_streaming = False
                self._is_paused_on_error = True
                # We don't clear _sent_lines here, because we want to be able to resume.
                # However, since we don't know for sure if the last commands were received,
                # the resume logic will need to be careful.
