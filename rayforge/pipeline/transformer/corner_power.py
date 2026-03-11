from __future__ import annotations
import math
import logging
from typing import List, Optional, Dict, Any, TYPE_CHECKING

from .base import OpsTransformer, ExecutionPhase
from ...core.ops import (
    Ops,
    Command,
    MovingCommand,
    MoveToCommand,
    LineToCommand,
    ArcToCommand,
    SetPowerCommand,
    SectionType,
    OpsSectionStartCommand,
    OpsSectionEndCommand,
)

if TYPE_CHECKING:
    from ...core.workpiece import WorkPiece
    from ...shared.tasker.proxy import BaseExecutionContext

logger = logging.getLogger(__name__)


class CornerPowerTransformer(OpsTransformer):
    """
    Reduces laser power at sharp corners to compensate for machine
    deceleration.

    When a machine follows a sharp-angle path, its motion controller slows
    down.  If the laser power remains constant, more energy is deposited at
    the corner, causing over-burning.

    This transformer detects corner vertices whose deviation angle exceeds
    ``min_angle_deg`` and inserts SetPower commands to lower the power during
    the inbound and outbound segments of each corner.

    The reduction is linear: corners with ``deviation >= full_angle_deg``
    receive ``min_power_factor * nominal_power``; gentler corners receive
    proportionally less reduction.

    Only operates on commands outside RASTER_FILL sections.
    """

    def __init__(
        self,
        enabled: bool = True,
        min_angle_deg: float = 30.0,
        full_angle_deg: float = 90.0,
        min_power_factor: float = 0.4,
    ):
        super().__init__(enabled=enabled)
        self.min_angle_deg = float(min_angle_deg)
        self.full_angle_deg = float(full_angle_deg)
        self.min_power_factor = max(0.0, min(1.0, float(min_power_factor)))

    @property
    def execution_phase(self) -> ExecutionPhase:
        return ExecutionPhase.GEOMETRY_REFINEMENT

    @property
    def label(self) -> str:
        return _("Corner Power Drop")

    @property
    def description(self) -> str:
        return _(
            "Reduces laser power at sharp corners to avoid over-burning"
            " during machine deceleration."
        )

    def _angle_deg(
        self,
        a: tuple,
        b: tuple,
        c: tuple,
    ) -> float:
        """
        Return the deviation angle (degrees) at vertex B for path A→B→C.
        0° = straight; 180° = U-turn.
        """
        ax, ay = b[0] - a[0], b[1] - a[1]
        bx, by = c[0] - b[0], c[1] - b[1]
        la = math.hypot(ax, ay)
        lb = math.hypot(bx, by)
        if la < 1e-9 or lb < 1e-9:
            return 0.0
        dot = (ax * bx + ay * by) / (la * lb)
        dot = max(-1.0, min(1.0, dot))
        return math.degrees(math.acos(dot))

    def _power_factor(self, angle_deg: float) -> float:
        """
        Return a power factor in [min_power_factor, 1.0] for the given angle.
        """
        if angle_deg <= self.min_angle_deg:
            return 1.0
        if angle_deg >= self.full_angle_deg:
            return self.min_power_factor
        t = (angle_deg - self.min_angle_deg) / (
            self.full_angle_deg - self.min_angle_deg
        )
        return 1.0 - t * (1.0 - self.min_power_factor)

    def run(
        self,
        ops: Ops,
        workpiece: Optional[WorkPiece] = None,
        context: Optional[BaseExecutionContext] = None,
    ) -> None:
        if not self.enabled:
            return

        ops.preload_state()

        commands = list(ops)
        if not commands:
            return

        # Build a positional index of cutting commands so we can look ahead.
        # We work with the final command list and do an insertion pass.
        new_commands: List[Command] = []
        in_raster = False

        # Track last two positions for angle calculation
        prev_pos: Optional[tuple] = None
        prev_prev_pos: Optional[tuple] = None
        prev_cmd_idx: Optional[int] = None  # index in new_commands

        for cmd in commands:
            if isinstance(cmd, OpsSectionStartCommand):
                if cmd.section_type == SectionType.RASTER_FILL:
                    in_raster = True
                prev_pos = prev_prev_pos = None
                prev_cmd_idx = None
                new_commands.append(cmd)
                continue

            if isinstance(cmd, OpsSectionEndCommand):
                if cmd.section_type == SectionType.RASTER_FILL:
                    in_raster = False
                prev_pos = prev_prev_pos = None
                prev_cmd_idx = None
                new_commands.append(cmd)
                continue

            if in_raster or not isinstance(cmd, MovingCommand):
                new_commands.append(cmd)
                continue

            cur_pos = cmd.end

            if isinstance(cmd, MoveToCommand):
                # Travel move resets path continuity
                prev_prev_pos = None
                prev_pos = cur_pos
                prev_cmd_idx = len(new_commands)
                new_commands.append(cmd)
                continue

            # Cutting command (LineToCommand or ArcToCommand)
            if prev_prev_pos is not None and prev_pos is not None:
                angle = self._angle_deg(prev_prev_pos, prev_pos, cur_pos)
                factor = self._power_factor(angle)

                if factor < 1.0 - 1e-4:
                    nominal_power = (
                        cmd.state.power
                        if cmd.state is not None
                        else 1.0
                    )
                    reduced_power = max(0.0, nominal_power * factor)

                    # Insert reduced power BEFORE this cutting move (corner
                    # deceleration on the inbound segment ended here; the
                    # accelerating outbound move is this cmd).
                    new_commands.append(
                        SetPowerCommand(round(reduced_power, 4))
                    )
                    new_commands.append(cmd)
                    new_commands.append(
                        SetPowerCommand(round(nominal_power, 4))
                    )
                    prev_prev_pos = prev_pos
                    prev_pos = cur_pos
                    continue

            prev_prev_pos = prev_pos
            prev_pos = cur_pos
            prev_cmd_idx = len(new_commands)
            new_commands.append(cmd)

        ops.commands = new_commands

    def to_dict(self) -> Dict[str, Any]:
        return {
            **super().to_dict(),
            "min_angle_deg": self.min_angle_deg,
            "full_angle_deg": self.full_angle_deg,
            "min_power_factor": self.min_power_factor,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CornerPowerTransformer":
        return cls(
            enabled=data.get("enabled", True),
            min_angle_deg=data.get("min_angle_deg", 30.0),
            full_angle_deg=data.get("full_angle_deg", 90.0),
            min_power_factor=data.get("min_power_factor", 0.4),
        )
