from __future__ import annotations
import logging
import math
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from .base import OpsProducer
from ...core.geo.constants import (
    CMD_TYPE_MOVE,
    CMD_TYPE_LINE,
    CMD_TYPE_ARC,
    CMD_TYPE_BEZIER,
    COL_TYPE,
    COL_X,
    COL_Y,
    COL_I,
    COL_J,
    COL_CW,
    COL_C1X,
    COL_C1Y,
    COL_C2X,
    COL_C2Y,
)
from ...core.ops import (
    Ops,
    SectionType,
    OpsSectionStartCommand,
    OpsSectionEndCommand,
)

if TYPE_CHECKING:
    from ...core.doc import Doc
    from ...core.geo import Geometry
    from ...core.step import Step

logger = logging.getLogger(__name__)

class GalvoProducer(OpsProducer):
    """
    Producer optimized for Galvo/Fiber laser marking.
    Handles high-speed mirror movements and specialized marking delays.
    """

    def __init__(
        self,
        marking_speed: float = 1000.0,
        travel_speed: float = 3000.0,
        laser_on_delay: int = 100,  # microseconds
        laser_off_delay: int = 100,
        poly_delay: int = 50,
        end_delay: int = 300,
        frequency: int = 20, # kHz
        power: float = 50.0,
    ):
        self.marking_speed = marking_speed
        self.travel_speed = travel_speed
        self.laser_on_delay = laser_on_delay
        self.laser_off_delay = laser_off_delay
        self.poly_delay = poly_delay
        self.end_delay = end_delay
        self.frequency = frequency
        self.power = power

    def produce(self, geo: Geometry, step: Step, doc: Doc) -> Ops:
        """
        Converts Geometry to Ops with Galvo-specific commands.
        """
        ops = Ops()
        if geo.data is None:
            return ops

        # Start a vector section
        ops.add(OpsSectionStartCommand(SectionType.VECTOR_OUTLINE))
        
        # Add Galvo parameter markers (if supported by subsequent encoders)
        # Note: These are often encoded directly into the driver protocol
        
        last_pos = (0.0, 0.0)
        for row in geo.data:
            cmd_type = row[COL_TYPE]
            end = (row[COL_X], row[COL_Y])
            
            if cmd_type == CMD_TYPE_MOVE:
                ops.move_to(end[0], end[1], speed=self.travel_speed)
            elif cmd_type == CMD_TYPE_LINE:
                ops.line_to(end[0], end[1], speed=self.marking_speed, power=self.power)
                # In a more advanced implementation, we would insert delay commands
                # ops.add(GalvoDelayCommand(self.poly_delay))
            elif cmd_type == CMD_TYPE_ARC:
                i, j, cw = row[COL_I], row[COL_J], bool(row[COL_CW])
                ops.arc_to(end[0], end[1], i, j, cw, speed=self.marking_speed, power=self.power)
            elif cmd_type == CMD_TYPE_BEZIER:
                c1 = (row[COL_C1X], row[COL_C1Y])
                c2 = (row[COL_C2X], row[COL_C2Y])
                ops.bezier_to(end[0], end[1], c1[0], c1[1], c2[0], c2[1], speed=self.marking_speed, power=self.power)
            
            last_pos = end

        ops.add(OpsSectionEndCommand())
        return ops

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.__class__.__name__,
            "marking_speed": self.marking_speed,
            "travel_speed": self.travel_speed,
            "laser_on_delay": self.laser_on_delay,
            "laser_off_delay": self.laser_off_delay,
            "poly_delay": self.poly_delay,
            "end_delay": self.end_delay,
            "frequency": self.frequency,
            "power": self.power,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GalvoProducer:
        return cls(
            marking_speed=data.get("marking_speed", 1000.0),
            travel_speed=data.get("travel_speed", 3000.0),
            laser_on_delay=data.get("laser_on_delay", 100),
            laser_off_delay=data.get("laser_off_delay", 100),
            poly_delay=data.get("poly_delay", 50),
            end_delay=data.get("end_delay", 300),
            frequency=data.get("frequency", 20),
            power=data.get("power", 50.0),
        )
