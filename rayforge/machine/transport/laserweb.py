import asyncio
import json
import logging
from typing import Optional, Any, Dict
from .websocket import WebSocketTransport
from .transport import TransportStatus

logger = logging.getLogger(__name__)

class LaserWebTransport(WebSocketTransport):
    """
    Transport for interacting with lw.comm-server (LaserWeb4 backend).
    Handles JSON framing and command protocols.
    """

    def __init__(self, uri: str):
        super().__init__(uri)
        # lw.comm-server usually expects JSON messages
        self._machine_id: Optional[str] = None

    async def _receive_loop(self) -> None:
        """
        Interprets incoming JSON messages from LaserWeb.
        """
        if self._websocket is None:
            return
        try:
            async for message in self._websocket:
                try:
                    data = json.loads(message)
                    if isinstance(data, dict):
                        # Handle LaserWeb specific messages
                        if "status" in data:
                            # Forward machine status
                            self.received.send(self, data=message.encode())
                        elif "hello" in data:
                            logger.info(f"LaserWeb: Handshake received: {data['hello']}")
                    else:
                        self.received.send(self, data=message.encode())
                except json.JSONDecodeError:
                    # Non-JSON message, forward as raw
                    if isinstance(message, str):
                        self.received.send(self, data=message.encode())
                    else:
                        self.received.send(self, data=message)
        except Exception as e:
            self._set_status(TransportStatus.ERROR, message=str(e))

    async def send_command(self, command: str, params: Optional[Dict[str, Any]] = None) -> None:
        """
        Sends a JSON-formatted command to lw.comm-server.
        """
        msg = {"command": command}
        if params:
            msg.update(params)
        
        await self.send(json.dumps(msg).encode())

    async def send_gcode(self, gcode: str) -> None:
        """
        Envelopes G-code into a LaserWeb command message.
        """
        await self.send_command("gcode", {"gcode": gcode})

    async def jog(self, axis: str, distance: float, speed: int) -> None:
        """
        Sends a jog command.
        """
        await self.send_command("jog", {"axis": axis, "distance": distance, "speed": speed})
