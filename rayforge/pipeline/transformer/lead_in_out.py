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
    SectionType,
    OpsSectionStartCommand,
    OpsSectionEndCommand,
)

if TYPE_CHECKING:
    from ...core.workpiece import WorkPiece
    from ...shared.tasker.proxy import BaseExecutionContext

logger = logging.getLogger(__name__)


class LeadInOutTransformer(OpsTransformer):
    """
    Adds a straight lead-in approach and lead-out exit to each vector
    cutting path.

    Lead-in: before the first cut, the laser approaches from an offset
    point along the same direction as the first cutting segment.  This
    avoids a dwell mark at the cut entry.

    Lead-out: after the last cut, the path is extended a short distance
    in the departure direction so the laser exits cleanly before lifting.

    Only operates on commands outside RASTER_FILL sections.
    """

    def __init__(
        self,
        enabled: bool = True,
        lead_in_mm: float = 1.0,
        lead_out_mm: float = 0.5,
    ):
        super().__init__(enabled=enabled)
        self.lead_in_mm = max(0.0, float(lead_in_mm))
        self.lead_out_mm = max(0.0, float(lead_out_mm))

    @property
    def execution_phase(self) -> ExecutionPhase:
        return ExecutionPhase.GEOMETRY_REFINEMENT

    @property
    def label(self) -> str:
        return _("Lead-In / Lead-Out")

    @property
    def description(self) -> str:
        return _(
            "Adds pre-cut approach and post-cut exit moves to avoid entry"
            " marks."
        )

    def run(
        self,
        ops: Ops,
        workpiece: Optional[WorkPiece] = None,
        context: Optional[BaseExecutionContext] = None,
    ) -> None:
        if not self.enabled:
            return
        if self.lead_in_mm == 0.0 and self.lead_out_mm == 0.0:
            return

        ops.preload_state()

        new_commands: List[Command] = []
        segment: List[Command] = []
        in_raster = False

        for cmd in ops:
            if isinstance(cmd, OpsSectionStartCommand):
                if cmd.section_type == SectionType.RASTER_FILL:
                    in_raster = True
                self._flush(segment, new_commands)
                segment = []
                new_commands.append(cmd)

            elif isinstance(cmd, OpsSectionEndCommand):
                if cmd.section_type == SectionType.RASTER_FILL:
                    in_raster = False
                self._flush(segment, new_commands)
                segment = []
                new_commands.append(cmd)

            elif in_raster:
                new_commands.append(cmd)

            elif isinstance(cmd, MoveToCommand):
                self._flush(segment, new_commands)
                segment = [cmd]

            else:
                segment.append(cmd)

        self._flush(segment, new_commands)
        ops.commands = new_commands

    def _flush(
        self, segment: List[Command], output: List[Command]
    ) -> None:
        if segment:
            output.extend(self._process_segment(segment))

    def _process_segment(
        self, segment: List[Command]
    ) -> List[Command]:
        cutting_idxs = [
            i
            for i, cmd in enumerate(segment)
            if isinstance(cmd, (LineToCommand, ArcToCommand))
        ]
        if not cutting_idxs:
            return list(segment)

        result = list(segment)

        if self.lead_in_mm > 0:
            result = self._apply_lead_in(result, cutting_idxs[0])
            # Recalculate after list modification
            cutting_idxs = [
                i
                for i, cmd in enumerate(result)
                if isinstance(cmd, (LineToCommand, ArcToCommand))
            ]

        if self.lead_out_mm > 0 and cutting_idxs:
            result = self._apply_lead_out(result, cutting_idxs[-1])

        return result

    def _apply_lead_in(
        self, segment: List[Command], first_cut_i: int
    ) -> List[Command]:
        travel_cmds = [
            cmd
            for cmd in segment[:first_cut_i]
            if isinstance(cmd, MoveToCommand)
        ]
        if not travel_cmds:
            return segment

        entry_point = travel_cmds[-1].end
        first_cut_end = segment[first_cut_i].end

        dx = first_cut_end[0] - entry_point[0]
        dy = first_cut_end[1] - entry_point[1]
        length = math.hypot(dx, dy)
        if length < 1e-9:
            return segment

        nx, ny = dx / length, dy / length
        approach = (
            entry_point[0] - nx * self.lead_in_mm,
            entry_point[1] - ny * self.lead_in_mm,
        )

        # Replace the last MoveToCommand with approach; add a LineTo entry
        pre = list(segment[:first_cut_i])
        for i in range(len(pre) - 1, -1, -1):
            if isinstance(pre[i], MoveToCommand):
                pre[i] = MoveToCommand(approach)
                pre.insert(i + 1, LineToCommand(entry_point))
                break

        return pre + list(segment[first_cut_i:])

    def _apply_lead_out(
        self, segment: List[Command], last_cut_i: int
    ) -> List[Command]:
        last_end = segment[last_cut_i].end
        prev_end = None
        for i in range(last_cut_i - 1, -1, -1):
            if isinstance(segment[i], MovingCommand):
                prev_end = segment[i].end
                break

        if prev_end is None:
            return segment

        dx = last_end[0] - prev_end[0]
        dy = last_end[1] - prev_end[1]
        length = math.hypot(dx, dy)
        if length < 1e-9:
            return segment

        nx, ny = dx / length, dy / length
        exit_pt = (
            last_end[0] + nx * self.lead_out_mm,
            last_end[1] + ny * self.lead_out_mm,
        )
        result = list(segment)
        result.insert(last_cut_i + 1, LineToCommand(exit_pt))
        return result

    def to_dict(self) -> Dict[str, Any]:
        return {
            **super().to_dict(),
            "lead_in_mm": self.lead_in_mm,
            "lead_out_mm": self.lead_out_mm,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LeadInOutTransformer":
        return cls(
            enabled=data.get("enabled", True),
            lead_in_mm=data.get("lead_in_mm", 1.0),
            lead_out_mm=data.get("lead_out_mm", 0.5),
        )
