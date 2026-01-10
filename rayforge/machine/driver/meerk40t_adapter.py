import logging
import asyncio
from typing import Any, List, Optional, Dict, Union, Callable, Awaitable
from ...context import RayforgeContext
from ...core.ops import Ops
from ...core.doc import Doc
from ...core.varset import VarSet, Var, ChoiceVar, IntVar
from ..models.machine import Machine, Axis
from ..models.laser import Laser
from .driver import Driver, DriverSetupError, DeviceState, DeviceStatus, TransportStatus

try:
    from meerk40t.kernel import Kernel
    from meerk40t.core.node.op_node import OpNode
    MEERK40T_AVAILABLE = True
except ImportError:
    MEERK40T_AVAILABLE = False
    Kernel = None

logger = logging.getLogger(__name__)

class Meerk40tAdapter(Driver):
    """
    Adapter bridging Rayforge Driver API to MeerK40t Kernel.
    This allows Rayforge to support K40, Moshi, Galvo, and other MeerK40t devices.
    """
    label = "MeerK40t Backend"
    subtitle = "Multi-hardware support (K40, Galvo, etc.)"
    supports_settings = True
    reports_granular_progress = True

    def __init__(self, context: RayforgeContext, machine: Machine):
        super().__init__(context, machine)
        self.kernel: Optional[Kernel] = None
        self.device_path: str = "0" # MeerK40t uses paths like '0', '1' for devices
        
    @classmethod
    def get_setup_vars(cls) -> VarSet:
        vs = VarSet()
        vs.add(ChoiceVar(
            "backend", 
            "Device Type", 
            choices=["grbl", "lihuiyu", "moshi", "balor", "dummy"],
            default="grbl",
            description="The underlying hardware driver to use in MeerK40t."
        ))
        vs.add(IntVar(
            "device_index",
            "Device Index",
            default=0,
            description="The index of the device if multiple are present."
        ))
        return vs

    @classmethod
    def precheck(cls, **kwargs: Any) -> None:
        if not MEERK40T_AVAILABLE:
            raise DriverSetupError("meerk40t package not installed")

    def _setup_implementation(self, **kwargs: Any) -> None:
        if not MEERK40T_AVAILABLE:
            raise DriverSetupError("meerk40t package not installed")
        
        backend = kwargs.get("backend", "grbl")
        index = kwargs.get("device_index", 0)
        self.device_path = str(index)

        self.kernel = Kernel("Rayforge")
        self.kernel.bootstrap()
        # Initialize selected device
        self.kernel.console(f"device add {backend} {self.device_path}\n")
        self.kernel.console(f"device {self.device_path}\n")

    def get_encoder(self):
        # Rayforge Ops -> MeerK40t Nodes or G-code
        # For now, we might rely on MeerK40t's internal generators
        return None

    async def _connect_implementation(self) -> None:
        if not self.kernel:
            raise DriverSetupError("Kernel not initialized")
        
        try:
            self.connection_status_changed.send(self, status=TransportStatus.CONNECTING)
            # MeerK40t connection is usually handled by the device service
            # We trigger it via console for now or direct service call
            self.kernel.console("open\n") 
            
            self.connection_status_changed.send(self, status=TransportStatus.CONNECTED)
            self.state = DeviceState(status=DeviceStatus.IDLE)
            self.state_changed.send(self, state=self.state)
        except Exception as e:
            logger.error(f"MeerK40t connection failed: {e}")
            self.connection_status_changed.send(self, status=TransportStatus.DISCONNECTED, message=str(e))
            raise

    async def cleanup(self):
        if self.kernel:
            self.kernel.console("close\n")
            self.kernel.shutdown()
        await super().cleanup()

    async def run(
        self,
        ops: Ops,
        doc: Doc,
        on_command_done: Optional[Callable[[int], Union[None, Awaitable[None]]]] = None,
    ) -> None:
        """
        Translates Rayforge Ops to MeerK40t operations and spools them.
        """
        if not self.kernel:
            raise DriverSetupError("Meerk40t kernel not initialized")

        self.state.status = DeviceStatus.RUN
        self.state_changed.send(self, state=self.state)
        
        try:
            from svgelements import Path, Move, Line, Arc, CubicBezier
            import math
            
            # Alternative: Use Geometry data for more uniform translation
            geo = ops.to_geometry()
            mk_path = Path()
            if geo.data is not None:
                from ...core.geo.constants import (
                    CMD_TYPE_MOVE, CMD_TYPE_LINE, CMD_TYPE_ARC, CMD_TYPE_BEZIER,
                    COL_TYPE, COL_X, COL_Y, COL_I, COL_J, COL_CW,
                    COL_C1X, COL_C1Y, COL_C2X, COL_C2Y
                )
                
                last_pt = (0.0, 0.0)
                for row in geo.data:
                    ctype = row[COL_TYPE]
                    end = (row[COL_X], row[COL_Y])
                    if ctype == CMD_TYPE_MOVE:
                        mk_path.append(Move(end))
                    elif ctype == CMD_TYPE_LINE:
                        mk_path.append(Line(last_pt, end))
                    elif ctype == CMD_TYPE_ARC:
                        # Simple linearization for now or robust Arc mapping
                        # MeerK40t likes specialized nodes, but Path works.
                        mk_path.append(Line(last_pt, end)) # Fallback to line
                    elif ctype == CMD_TYPE_BEZIER:
                        mk_path.append(CubicBezier(
                            last_pt, (row[COL_C1X], row[COL_C1Y]), (row[COL_C2X], row[COL_C2Y]), end
                        ))
                    last_pt = end

            # 2. Inject into MeerK40t
            elements = self.kernel.elements
            elements.activate_service(self.device_path)
            
            # Clear previous elements to avoid accumulation
            elements.clear_all()
            
            # Add path as a node
            node = elements.elem_branch.add(
                path=mk_path,
                type="elem path",
                stroke="black"
            )
            
            # Select the node for planning
            elements.set_selected([node])
            
            # 3. Spool the job
            # Standard MeerK40t planning sequence:
            # - plan0: The default plan
            # - copy: Copy elements to plan
            # - pre-process: Handle offsets/scaling
            # - validate: Ensure ops are valid
            # - preop: Handle pre-job gcode/commands
            # - optimize: Path optimization
            # - spool: Send to device spooler
            self.kernel.console("plan0 clear copy pre-process validate preop optimize spool\n")
            
            logger.info("MeerK40tAdapter: Spooling job to MeerK40t kernel")
            
        except ImportError as e:
            logger.error(f"MeerK40t component missing: {e}")
            raise DriverSetupError(f"Protocol error: {e}")
        finally:
            self.state.status = DeviceStatus.IDLE
            self.state_changed.send(self, state=self.state)
            self.job_finished.send(self)

    async def run_raw(self, command: str) -> None:
        if self.kernel:
            self.kernel.console(command + "\n")

    async def cancel(self) -> None:
        await self.run_raw("estop")

    async def home(self, axes: Optional[Axis] = None) -> None:
        await self.run_raw("home")

    async def move_to(self, pos_x: float, pos_y: float) -> None:
        await self.run_raw(f"move {pos_x}mm {pos_y}mm")

    async def jog(self, axis: Axis, distance: float, speed: int) -> None:
        # Simple jog implementation via console
        axis_name = "x" if axis & Axis.X else "y" if axis & Axis.Y else "z"
        await self.run_raw(f"jog {axis_name} {distance}mm")
