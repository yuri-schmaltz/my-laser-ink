# flake8: noqa:F401
import inspect
from .base import OpsTransformer, ExecutionPhase
from .multipass import MultiPassTransformer
from .optimize import Optimize
from .overscan import OverscanTransformer
from .smooth import Smooth
from .tabs import TabOpsTransformer
from .sort_shapes import TopologySorter
from .lead_in_out import LeadInOutTransformer
from .corner_power import CornerPowerTransformer
from .array import ArrayTransformer

transformer_by_name = dict(
    (name, obj)
    for name, obj in locals().items()
    if inspect.isclass(obj)
    and issubclass(obj, OpsTransformer)
    and not inspect.isabstract(obj)
)

__all__ = [
    "OpsTransformer",
    "ExecutionPhase",
    "MultiPassTransformer",
    "Optimize",
    "OverscanTransformer",
    "Smooth",
    "TabOpsTransformer",
    "transformer_by_name",
    "LeadInOutTransformer",
    "CornerPowerTransformer",
    "ArrayTransformer",
]
