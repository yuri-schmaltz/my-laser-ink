from __future__ import annotations
import logging
from typing import TYPE_CHECKING, Optional, Union
import ezdxf
from svgelements import SVG, Path, Move, Line, Arc, CubicBezier, Point

if TYPE_CHECKING:
    from .ops import Ops
    from ..core.geo import Geometry

logger = logging.getLogger(__name__)

class Exporter:
    """
    Service for exporting Ops or Geometry to standard vector formats (SVG, DXF).
    """

    @staticmethod
    def save(source: Union[Ops, Geometry], filename: str):
        """Dispatches to the correct exporter based on file extension."""
        if filename.lower().endswith(".svg"):
            Exporter.to_svg(source, filename)
        elif filename.lower().endswith(".dxf"):
            Exporter.to_dxf(source, filename)
        else:
            raise ValueError(f"Unsupported export format for extension: {filename}")

    @staticmethod
    def _get_geo(source: Union[Ops, Geometry]) -> Geometry:
        from ..core.ops import Ops
        if isinstance(source, Ops):
            return source.to_geometry()
        return source

    @staticmethod
    def to_svg(source: Union[Ops, Geometry], filename: str):
        """Exports the given source to an SVG file."""
        geo = Exporter._get_geo(source)
        svg_doc = SVG()
        svg_path = Path()
        
        if geo.data is not None:
            from ..core.geo.constants import (
                CMD_TYPE_MOVE, CMD_TYPE_LINE, CMD_TYPE_ARC, CMD_TYPE_BEZIER,
                COL_TYPE, COL_X, COL_Y, COL_I, COL_J, COL_CW,
                COL_C1X, COL_C1Y, COL_C2X, COL_C2Y
            )
            
            import math
            last_pos = (0.0, 0.0)
            for row in geo.data:
                cmd_type = row[COL_TYPE]
                end = (row[COL_X], row[COL_Y])
                
                if cmd_type == CMD_TYPE_MOVE:
                    svg_path.append(Move(end))
                elif cmd_type == CMD_TYPE_LINE:
                    svg_path.append(Line(last_pos, end))
                elif cmd_type == CMD_TYPE_ARC:
                    i, j, cw = row[COL_I], row[COL_J], bool(row[COL_CW])
                    center = (last_pos[0] + i, last_pos[1] + j)
                    radius = math.sqrt(i**2 + j**2)
                    
                    start_angle = math.atan2(-j, -i)
                    end_angle = math.atan2(end[1] - center[1], end[0] - center[0])
                    
                    angle_diff = end_angle - start_angle
                    if cw:
                        if angle_diff > 0: angle_diff -= 2 * math.pi
                    else:
                        if angle_diff < 0: angle_diff += 2 * math.pi
                    
                    large_arc = 1 if abs(angle_diff) > math.pi else 0
                    sweep = 0 if cw else 1 # SVG sweep: 0=CW, 1=CCW
                    
                    from svgelements import Arc as SvgArc
                    svg_path.append(SvgArc(
                        start=last_pos,
                        radius=(radius, radius),
                        rotation=0,
                        large_arc=large_arc,
                        sweep=sweep,
                        end=end
                    ))
                elif cmd_type == CMD_TYPE_BEZIER:
                    svg_path.append(CubicBezier(
                        last_pos, 
                        (row[COL_C1X], row[COL_C1Y]), 
                        (row[COL_C2X], row[COL_C2Y]), 
                        end
                    ))
                last_pos = end

        svg_doc.append(svg_path)
        with open(filename, "w") as f:
            f.write(svg_doc.string())
        logger.info(f"Exported SVG to {filename}")

    @staticmethod
    def to_dxf(source: Union[Ops, Geometry], filename: str):
        """Exports the given source to a DXF file."""
        geo = Exporter._get_geo(source)
        doc = ezdxf.new()
        msp = doc.modelspace()

        if geo.data is not None:
            from ..core.geo.constants import (
                CMD_TYPE_MOVE, CMD_TYPE_LINE, CMD_TYPE_ARC, CMD_TYPE_BEZIER,
                COL_TYPE, COL_X, COL_Y, COL_I, COL_J, COL_CW,
                COL_C1X, COL_C1Y, COL_C2X, COL_C2Y
            )
            
            import math
            last_pos = (0.0, 0.0)
            for row in geo.data:
                cmd_type = row[COL_TYPE]
                end = (row[COL_X], row[COL_Y])
                
                if cmd_type == CMD_TYPE_LINE:
                    msp.add_line(last_pos, end)
                elif cmd_type == CMD_TYPE_ARC:
                    center = (last_pos[0] + row[COL_I], last_pos[1] + row[COL_J])
                    radius = math.sqrt(row[COL_I]**2 + row[COL_J]**2)
                    start_angle = math.degrees(math.atan2(-row[COL_J], -row[COL_I]))
                    end_angle = math.degrees(math.atan2(end[1] - center[1], end[0] - center[0]))
                    
                    if row[COL_CW]:
                        msp.add_arc(center, radius, end_angle, start_angle)
                    else:
                        msp.add_arc(center, radius, start_angle, end_angle)
                elif cmd_type == CMD_TYPE_BEZIER:
                    pts = [last_pos, (row[COL_C1X], row[COL_C1Y]), (row[COL_C2X], row[COL_C2Y]), end]
                    msp.add_bezier(pts)
                
                last_pos = end

        doc.saveas(filename)
        logger.info(f"Exported DXF to {filename}")
