from typing import Dict, Type
from .base import StepComponentSettingsWidget
from .depth_engraver import DepthEngraverSettingsWidget
from .contour import ContourProducerSettingsWidget
from .galvo import GalvoProducerSettingsWidget
from .frame import FrameProducerSettingsWidget
from .material_test_grid import MaterialTestGridSettingsWidget
from .multipass import MultiPassSettingsWidget
from .optimize import OptimizeSettingsWidget
from .overscan import OverscanSettingsWidget
from .rasterizer import RasterizerSettingsWidget
from .shrinkwrap import ShrinkWrapProducerSettingsWidget
from .smooth import SmoothSettingsWidget
from .advanced_rasterizer import AdvancedRasterizerSettingsWidget
from .topology_sorter import TopologySorterSettingsWidget
from .lead_in_out import LeadInOutSettingsWidget
from .corner_power import CornerPowerSettingsWidget
from .array import ArraySettingsWidget


# This registry maps the class names of pipeline components (str)
# to their corresponding UI widget classes (Type).
WIDGET_REGISTRY: Dict[str, Type[StepComponentSettingsWidget]] = {
    "DepthEngraver": DepthEngraverSettingsWidget,
    "ContourProducer": ContourProducerSettingsWidget,
    "GalvoProducer": GalvoProducerSettingsWidget,
    "FrameProducer": FrameProducerSettingsWidget,
    "MaterialTestGridProducer": MaterialTestGridSettingsWidget,
    "MultiPassTransformer": MultiPassSettingsWidget,
    "Optimize": OptimizeSettingsWidget,
    "OverscanTransformer": OverscanSettingsWidget,
    "Rasterizer": RasterizerSettingsWidget,
    "ShrinkWrapProducer": ShrinkWrapProducerSettingsWidget,
    "Smooth": SmoothSettingsWidget,
    "AdvancedRasterizer": AdvancedRasterizerSettingsWidget,
    "TopologySorter": TopologySorterSettingsWidget,
    "LeadInOutTransformer": LeadInOutSettingsWidget,
    "CornerPowerTransformer": CornerPowerSettingsWidget,
    "ArrayTransformer": ArraySettingsWidget,
}

__all__ = [
    "WIDGET_REGISTRY",
    "DepthEngraverSettingsWidget",
    "ContourProducerSettingsWidget",
    "GalvoProducerSettingsWidget",
    "FrameProducerSettingsWidget",
    "MaterialTestGridSettingsWidget",
    "MultiPassSettingsWidget",
    "OptimizeSettingsWidget",
    "OverscanSettingsWidget",
    "RasterizerSettingsWidget",
    "ShrinkWrapProducerSettingsWidget",
    "SmoothSettingsWidget",
    "AdvancedRasterizerSettingsWidget",
    "TopologySorterSettingsWidget",
    "LeadInOutSettingsWidget",
    "CornerPowerSettingsWidget",
    "ArraySettingsWidget",
    "StepComponentSettingsWidget",
]
