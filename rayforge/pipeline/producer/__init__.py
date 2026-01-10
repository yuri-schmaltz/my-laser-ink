# flake8: noqa:F401
import inspect
from .base import OpsProducer, CutSide
from .depth import DepthEngraver
from .contour import ContourProducer
from .frame import FrameProducer
from .material_test_grid import MaterialTestGridProducer, MaterialTestGridType
from .shrinkwrap import ShrinkWrapProducer
from .rasterize import Rasterizer
from .advanced_raster import AdvancedRasterizer
from .galvo import GalvoProducer

producer_by_name = dict(
    [
        (name, obj)
        for name, obj in locals().items()
        if inspect.isclass(obj)
        and issubclass(obj, OpsProducer)
        and not inspect.isabstract(obj)
    ]
)

__all__ = [
    "OpsProducer",
    "CutSide",
    "DepthEngraver",
    "ContourProducer",
    "FrameProducer",
    "MaterialTestGridProducer",
    "MaterialTestGridType",
    "ShrinkWrapProducer",
    "Rasterizer",
    "AdvancedRasterizer",
    "GalvoProducer",
    "producer_by_name",
]
