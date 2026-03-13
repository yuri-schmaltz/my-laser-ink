from __future__ import annotations
import math
from typing import Optional, Dict, Any

from .base import OpsTransformer, ExecutionPhase
from ...core.workpiece import WorkPiece
from ...core.ops import Ops
from ...shared.tasker.proxy import BaseExecutionContext


class MultiPassTransformer(OpsTransformer):
    """
    Repeats the sequence of operations multiple times.

    This transformer is typically used in the "post-assembly" phase of a Step
    to create multiple cutting or engraving passes over the entire assembled
    geometry. It can also apply a Z-axis step-down for each subsequent pass,
    which is useful for cutting through thick materials.
    """

    def __init__(
        self,
        enabled: bool = True,
        passes: int = 1,
        z_step_down: float = 0.0,
        finish_object_first: bool = False,
    ):
        """
        Initializes the MultiPassTransformer.

        Args:
            enabled: Whether the transformer is active.
            passes: The total number of passes to perform. Must be >= 1.
            z_step_down: The distance to move down the Z-axis after each
                         pass. A positive value indicates downward movement.
        """
        super().__init__(enabled=enabled)
        self._passes: int = 1
        self._z_step_down: float = 0.0
        self._finish_object_first: bool = False

        # Use property setters to ensure validation logic is applied
        self.passes = passes
        self.z_step_down = z_step_down
        self.finish_object_first = finish_object_first

    @property
    def execution_phase(self) -> ExecutionPhase:
        """Multi-pass duplicates the final path, so it runs late."""
        return ExecutionPhase.POST_PROCESSING

    @property
    def passes(self) -> int:
        """The total number of passes to perform (e.g., 3 means 3 total)."""
        return self._passes

    @passes.setter
    def passes(self, value: int):
        """Sets the total number of passes, ensuring it's at least 1."""
        new_value = max(1, int(value))
        if self._passes != new_value:
            self._passes = new_value
            self.changed.send(self)

    @property
    def z_step_down(self) -> float:
        """The amount to step down in Z for each pass after the first."""
        return self._z_step_down

    @z_step_down.setter
    def z_step_down(self, value: float):
        """Sets the Z step-down value."""
        new_value = float(value)
        if not math.isclose(self._z_step_down, new_value):
            self._z_step_down = new_value
            self.changed.send(self)

    @property
    def finish_object_first(self) -> bool:
        """
        Whether to finish all passes for each object before moving to
        the next.
        """
        return self._finish_object_first

    @finish_object_first.setter
    def finish_object_first(self, value: bool):
        """Sets the finish_object_first mode."""
        new_value = bool(value)
        if self._finish_object_first != new_value:
            self._finish_object_first = new_value
            self.changed.send(self)

    @property
    def label(self) -> str:
        return _("Multi-Pass")

    @property
    def description(self) -> str:
        return _(
            "Repeats the path multiple times, optionally stepping down in Z."
        )

    def run(
        self,
        ops: Ops,
        workpiece: Optional[WorkPiece] = None,
        context: Optional[BaseExecutionContext] = None,
    ) -> None:
        """
        Executes the multi-pass transformation on the Ops object.

        Args:
            ops: The Ops object to transform in-place.
            context: Execution context for cancellation (not used here).
        """
        # No-op if only one pass and no Z movement is needed.
        if self.passes <= 1 and self._z_step_down == 0.0:
            return

        # No-op if there are no commands to duplicate.
        if ops.is_empty():
            return

        if self._finish_object_first:
            self._run_optimized(ops)
        else:
            self._run_global(ops)

    def _run_global(self, ops: Ops) -> None:
        """Repeats the entire sequence of operations multiple times."""
        # Make a pristine copy of the original commands for subsequent passes.
        original_ops = ops.copy()

        # Generate and append subsequent passes
        for i in range(1, self.passes):
            # Create a fresh copy for this pass
            pass_ops = original_ops.copy()

            # Apply Z step-down if configured
            if self._z_step_down != 0.0:
                z_offset = i * self._z_step_down
                # Translate by a negative amount to move down the Z axis
                pass_ops.translate(0, 0, -abs(z_offset))

            ops.extend(pass_ops)

    def _run_optimized(self, ops: Ops) -> None:
        """
        Repeats each object/segment multiple times before moving to the next.
        """
        # 1. Break down into segments (contours)
        segments = list(ops.segments())
        if not segments:
            return

        # 2. Reconstruct Ops with repeated segments
        new_ops = Ops()
        for segment in segments:
            # Create a localized Ops container for this segment
            seg_ops = Ops()
            seg_ops.commands = segment

            # Add the first pass
            new_ops.extend(seg_ops)

            # Add subsequent passes for THIS segment
            for i in range(1, self.passes):
                pass_ops = seg_ops.copy()
                if self._z_step_down != 0.0:
                    z_offset = i * self._z_step_down
                    pass_ops.translate(0, 0, -abs(z_offset))
                new_ops.extend(pass_ops)

        # 3. Update original ops in-place
        ops.commands = new_ops.commands

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the transformer's configuration to a dictionary."""
        return {
            **super().to_dict(),
            "passes": self.passes,
            "z_step_down": self.z_step_down,
            "finish_object_first": self.finish_object_first,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MultiPassTransformer":
        """Creates a MultiPassTransformer instance from a dictionary."""
        if data.get("name") != cls.__name__:
            raise ValueError(
                f"Mismatched transformer name: expected {cls.__name__},"
                f" got {data.get('name')}"
            )
        return cls(
            enabled=data.get("enabled", True),
            passes=data.get("passes", 1),
            z_step_down=data.get("z_step_down", 0.0),
            finish_object_first=data.get("finish_object_first", False),
        )
