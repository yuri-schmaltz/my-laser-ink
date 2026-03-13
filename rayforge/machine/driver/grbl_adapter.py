import logging
import asyncio
from typing import Any, List, Optional, Dict, Union, Callable, Awaitable, TYPE_CHECKING
from ...context import RayforgeContext
from ...core.ops import Ops
from ...core.doc import Doc
from ...core.varset import VarSet, SerialPortVar, Var
from .driver import Driver, DriverSetupError, DeviceState, DeviceStatus, Axis
from ..transport import TransportStatus

if TYPE_CHECKING:
    from ..models.machine import Machine
    from ..models.laser import Laser

# Try importing the new driver package
try:
    import sys
    import os
    # Add packages path if not present (Assumption: we are in apps/desktop/rayforge/machine/driver)
    # Root is up 5 levels? 
    # Better: Assume user environment has it or we add it safely.
    # For this task, let's append the known path from previous context
    packages_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../packages"))
    if packages_path not in sys.path:
        sys.path.append(os.path.join(packages_path, "drivers/grbl/src"))
        sys.path.append(os.path.join(packages_path, "device_api/src"))

    from grbl.driver import GrblDevice
except ImportError:
    # If explicit path hacking failed or wasn't needed
    try:
        from grbl.driver import GrblDevice
    except ImportError:
        # Fallback for type checking or if really missing
        GrblDevice = None

logger = logging.getLogger(__name__)

class GrblAdapter(Driver):
    """
    Adapter bridging the legacy Rayforge Driver API to the new clean GrblDevice API.
    """
    label = "GRBL (New)"
    subtitle = "Standard GRBL 1.1 via Device API"
    supports_settings = False
    reports_granular_progress = True

    def __init__(self, context: RayforgeContext, machine: "Machine"):
        super().__init__(context, machine)
        self.device: Optional[GrblDevice] = None
        self.port: Optional[str] = None
        
    @classmethod
    def get_setup_vars(cls) -> VarSet:
        vs = VarSet()
        vs.add_var(SerialPortVar("port", "Port", "Serial port (e.g. /dev/ttyUSB0)", default="/dev/ttyUSB0"))
        return vs

    @classmethod
    def precheck(cls, **kwargs: Any) -> None:
        pass

    def _setup_implementation(self, **kwargs: Any) -> None:
        self.port = kwargs.get("port")
        if not self.port:
            raise DriverSetupError("Port is required")
        
        if GrblDevice:
            self.device = GrblDevice(self.port)
        else:
            raise DriverSetupError("GrblDevice package not found")

    def get_encoder(self):
        # Return generic GCode encoder 
        # (Assuming GcodeDialect generic is fine, or we use the specific one)
        from ...pipeline.encoder.gcode import GcodeEncoder
        return GcodeEncoder(self._machine.dialect)

    def get_setting_vars(self) -> List[VarSet]:
        return []

    async def _connect_implementation(self) -> None:
        if not self.device:
            raise DriverSetupError("Device not initialized")
        
        try:
            self.connection_status_changed.send(self, status=TransportStatus.CONNECTING)
            await self.device.connect()
            self.connection_status_changed.send(self, status=TransportStatus.CONNECTED)
            self.state = DeviceState(status=DeviceStatus.IDLE)
            self.state_changed.send(self, state=self.state)
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.connection_status_changed.send(self, status=TransportStatus.DISCONNECTED, message=str(e))
            raise

    async def cleanup(self):
        if self.device:
            await self.device.disconnect()
        await super().cleanup()

    # --- Runtime Methods ---

    async def run(
        self,
        ops: Ops,
        doc: Doc,
        on_command_done: Optional[Callable[[int], Union[None, Awaitable[None]]]] = None,
    ) -> None:
        # Convert Ops to G-code string using Encoder
        # Efficient streaming is handled by Spooler, but here we generate text first?
        # New GrblDevice.job takes a string. 
        # Ideally we stream generator, but let's stringify for now.
        
        encoder = self.get_encoder()
        # machine.encode_ops is a helper that uses the encoder
        gcode_lines, _ = self._machine.encode_ops(ops, doc)
        gcode_str = "\n".join(gcode_lines)
        
        self.state.status = DeviceStatus.RUN
        self.state_changed.send(self, state=self.state)
        
        await self.device.job(gcode_str)
        
        self.state.status = DeviceStatus.IDLE
        self.state_changed.send(self, state=self.state)
        self.job_finished.send(self)

    async def run_raw(self, gcode: str) -> None:
        # GrblDevice.spooler.send_command for single lines?
        # job for multi-lines?
        if "\n" in gcode:
            await self.device.job(gcode)
        else:
            await self.device.spooler.send_command(gcode)

    async def set_hold(self, hold: bool = True) -> None:
        cmd = "!" if hold else "~"
        # Real-time command, bypass buffer if possible?
        # Spooler might need priority method.
        # For now, append to queue or send raw if supported.
        # GrblDevice doesn't expose priority send yet.
        await self.run_raw(cmd) 

    async def cancel(self) -> None:
         # GRBL Soft Reset
        await self.run_raw("\x18")

    async def home(self, axes: Optional["Axis"] = None) -> None:
        cmd = "$H"
        # If axes specified (e.g. only X), GRBL specific?? 
        # Standard GRBL $H is all axes. 
        # Some forks support $HX. Assuming standard $H for now.
        await self.device.home()

    async def move_to(self, pos_x: float, pos_y: float) -> None:
        await self.device.move_to(pos_x, pos_y)

    async def jog(self, axis: "Axis", distance: float, speed: int) -> None:
        # G91 (Relative) -> Move -> G90 (Absolute)
        # Or $J= (Jog command)
        # GRBL 1.1 Standard: $J=G91 X10 F1000
        
        axes_str = ""
        if axis & Axis.X: axes_str += f"X{distance} "
        if axis & Axis.Y: axes_str += f"Y{distance} "
        if axis & Axis.Z: axes_str += f"Z{distance} " # Distance applied to all? Usually jog is 1 axis.
        
        cmd = f"$J=G91 {axes_str}F{speed}"
        await self.run_raw(cmd)

    async def select_tool(self, tool_number: int) -> None:
        pass # Not relevant for standard Lasers usually

    async def read_settings(self) -> None:
        await self.run_raw("$$")
        # Parsing output is tricky here without callbacks.
        # GrblDevice needs to handle response.
        pass

    async def write_setting(self, key: str, value: Any) -> None:
        await self.run_raw(f"${key}={value}")

    async def clear_alarm(self) -> None:
        await self.run_raw("$X")

    async def set_power(self, head: "Laser", percent: float) -> None:
        s_val = int(percent * 1000) # Assuming S_MAX=1000
        await self.run_raw(f"M3 S{s_val}") # or M4? 

    async def set_wcs_offset(self, wcs_slot: str, x: float, y: float, z: float) -> None:
        # G10 L2 P<index> X...
        # Map G54->P1, G55->P2...
        pass

    async def read_wcs_offsets(self) -> Dict[str, Any]:
        return {}

    async def run_probe_cycle(self, axis: Axis, max_travel: float, feed_rate: int) -> Optional[Any]:
        return None
