from __future__ import annotations
import math
from typing import Optional, Dict, Any

from .base import OpsTransformer, ExecutionPhase
from ...core.workpiece import WorkPiece
from ...core.ops import Ops
from ...shared.tasker.proxy import BaseExecutionContext


class ArrayTransformer(OpsTransformer):
    """
    Duplicates the assembled job ops in a rows × cols grid.

    Each copy is shifted by (col * x_spacing_mm, row * y_spacing_mm)
    relative to the original at position (0, 0).  This transformer runs
    in the POST_PROCESSING phase so it operates on the final, merged ops
    that already incorporate all per-workpiece transformations.
    """

    def __init__(
        self,
        enabled: bool = True,
        rows: int = 1,
        cols: int = 1,
        x_spacing_mm: float = 10.0,
        y_spacing_mm: float = 10.0,
    ):
        super().__init__(enabled=enabled)
        self._rows: int = 1
        self._cols: int = 1
        self._x_spacing_mm: float = 0.0
        self._y_spacing_mm: float = 0.0

        self.rows = rows
        self.cols = cols
        self.x_spacing_mm = x_spacing_mm
        self.y_spacing_mm = y_spacing_mm

    @property
    def execution_phase(self) -> ExecutionPhase:
        return ExecutionPhase.POST_PROCESSING

    @property
    def rows(self) -> int:
        return self._rows

    @rows.setter
    def rows(self, value: int):
        new_value = max(1, int(value))
        if self._rows != new_value:
            self._rows = new_value
            self.changed.send(self)

    @property
    def cols(self) -> int:
        return self._cols

    @cols.setter
    def cols(self, value: int):
        new_value = max(1, int(value))
        if self._cols != new_value:
            self._cols = new_value
            self.changed.send(self)

    @property
    def x_spacing_mm(self) -> float:
        return self._x_spacing_mm

    @x_spacing_mm.setter
    def x_spacing_mm(self, value: float):
        new_value = float(value)
        if not math.isclose(self._x_spacing_mm, new_value):
            self._x_spacing_mm = new_value
            self.changed.send(self)

    @property
    def y_spacing_mm(self) -> float:
        return self._y_spacing_mm

    @y_spacing_mm.setter
    def y_spacing_mm(self, value: float):
        new_value = float(value)
        if not math.isclose(self._y_spacing_mm, new_value):
            self._y_spacing_mm = new_value
            self.changed.send(self)

    @property
    def label(self) -> str:
        return _("Array (Step & Repeat)")

    @property
    def description(self) -> str:
        return _(
            "Repeats the job geometry in a rows × columns grid"
            " with configurable spacing."
        )

    def run(
        self,
        ops: Ops,
        workpiece: Optional[WorkPiece] = None,
        context: Optional[BaseExecutionContext] = None,
    ) -> None:
        if self.rows <= 1 and self.cols <= 1:
            return
        if ops.is_empty():
            return

        original = ops.copy()

        for row in range(self.rows):
            for col in range(self.cols):
                if row == 0 and col == 0:
                    continue
                copy_ops = original.copy()
                copy_ops.translate(
                    col * self._x_spacing_mm,
                    row * self._y_spacing_mm,
                )
                ops.extend(copy_ops)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **super().to_dict(),
            "rows": self.rows,
            "cols": self.cols,
            "x_spacing_mm": self.x_spacing_mm,
            "y_spacing_mm": self.y_spacing_mm,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArrayTransformer":
        if data.get("name") != cls.__name__:
            raise ValueError(
                f"Mismatched transformer name: expected {cls.__name__},"
                f" got {data.get('name')}"
            )
        return cls(
            enabled=data.get("enabled", True),
            rows=data.get("rows", 1),
            cols=data.get("cols", 1),
            x_spacing_mm=data.get("x_spacing_mm", 10.0),
            y_spacing_mm=data.get("y_spacing_mm", 10.0),
        )
