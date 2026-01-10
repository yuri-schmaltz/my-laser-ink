from pydantic import BaseModel, Field
from typing import List, Literal, Optional

class Operation(BaseModel):
    name: str
    type: Literal["vector", "raster"]
    speed: float = Field(..., description="Speed in mm/min")
    power: float = Field(..., description="Power in percent 0-100")
    passes: int = Field(1, description="Number of passes")
    resolution_mm: Optional[float] = Field(None, description="Raster step size (e.g. 0.1mm)")

class Material(BaseModel):
    name: str
    thickness: float = Field(..., description="Thickness in mm")
    operations: List[Operation] = []

class MaterialLibrary(BaseModel):
    name: str
    materials: List[Material] = []
