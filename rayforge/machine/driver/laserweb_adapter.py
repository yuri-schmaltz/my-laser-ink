import logging
import asyncio
from typing import Any, List, Optional, Dict, Union, Callable, Awaitable
from ...context import RayforgeContext
from ...core.ops import Ops
from ...core.doc import Doc
from ...core.varset import VarSet, HostnameVar
from ..models.machine import Machine, Axis
from ..models.laser import Laser
from .driver import Driver, DriverSetupError, DeviceState, DeviceStatus, TransportStatus
from ..transport.laserweb import LaserWebTransport

logger = logging.getLogger(__name__)

class LaserWebAdapter(Driver):
    """
    Adapter for remote machine control via LaserWeb (lw.comm-server).
    """
    label = "LaserWeb Remote"
    subtitle = "Control machines over the network via LaserWeb4"
    supports_settings = False # Let LaserWeb handle machine settings
    reports_granular_progress = True

    def __init__(self, context: RayforgeContext, machine: Machine):
        super().__init__(context, machine)
        self.transport: Optional[LaserWebTransport] = None
        
    @classmethod
    def get_setup_vars(cls) -> VarSet:
        vs = VarSet()
        vs.add(HostnameVar(
            "url", 
            "Server URL", 
            default="ws://localhost:8000",
            description="The WebSocket URL of the lw.comm-server instance."
        ))
        return vs

    @classmethod
    def precheck(cls, **kwargs: Any) -> None:
        if not kwargs.get("url"):
            raise DriverSetupError("LaserWeb server URL is required")

    def _setup_implementation(self, **kwargs: Any) -> None:
        url = kwargs.get("url")
        self.transport = LaserWebTransport(url)
        # Connect internal transport signals if needed
        self.transport.status_changed.connect(self._on_transport_status_changed)

    def _on_transport_status_changed(self, sender, status: TransportStatus, message: Optional[str] = None):
        self.connection_status_changed.send(self, status=status, message=message)

    def get_encoder(self):
        # LaserWeb usually takes G-code. 
        # We can use the standard GcodeEncoder.
        from ...pipeline.encoder.gcode import GcodeEncoder
        return GcodeEncoder(self._machine.dialect)

    async def _connect_implementation(self) -> None:
        if not self.transport:
            raise DriverSetupError("Transport not initialized")
        
        await self.transport.connect()
        self.state = DeviceState(status=DeviceStatus.IDLE)
        self.state_changed.send(self, state=self.state)

    async def cleanup(self):
        if self.transport:
            await self.transport.disconnect()
        await super().cleanup()

    async def run(
        self,
        ops: Ops,
        doc: Doc,
        on_command_done: Optional[Callable[[int], Union[None, Awaitable[None]]]] = None,
    ) -> None:
        if not self.transport:
            raise DriverSetupError("Not connected")

        encoder = self.get_encoder()
        gcode_lines, _ = self._machine.encode_ops(ops, doc)
        gcode_str = "\n".join(gcode_lines)
        
        self.state.status = DeviceStatus.RUN
        self.state_changed.send(self, state=self.state)
        
        await self.transport.send_gcode(gcode_str)
        
        self.state.status = DeviceStatus.IDLE
        self.state_changed.send(self, state=self.state)
        self.job_finished.send(self)

    async def run_raw(self, gcode: str) -> None:
        if self.transport:
            await self.transport.send_gcode(gcode)

    async def cancel(self) -> None:
        if self.transport:
            await self.transport.send_command("abort")

    async def home(self, axes: Optional[Axis] = None) -> None:
        await self.run_raw("$H")

    async def move_to(self, pos_x: float, pos_y: float) -> None:
        await self.run_raw(f"G0 X{pos_x} Y{pos_y}")

    async def jog(self, axis: Axis, distance: float, speed: int) -> None:
        axis_str = "X" if axis & Axis.X else "Y" if axis & Axis.Y else "Z"
        if self.transport:
             await self.transport.jog(axis_str, distance, speed)
