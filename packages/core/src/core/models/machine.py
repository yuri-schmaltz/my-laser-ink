from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class MachineDims(BaseModel):
    width: float = Field(..., description="Working area width in mm")
    height: float = Field(..., description="Working area height in mm")
    auto_home: bool = Field(True, description="Whether to home on connect")

class MachineConnection(BaseModel):
    port: str = Field(..., description="Serial port path connection string")
    baud: int = Field(115200, description="Baud rate")

class LaserConfig(BaseModel):
    max_power: int = Field(1000, description="S-value corresponding to 100% power")
    max_speed: int = Field(6000, description="Maximum travel speed in mm/min")

class MachineProfile(BaseModel):
    name: str
    driver: str = Field("grbl", description="Driver identifier")
    dimensions: MachineDims
    connection: MachineConnection
    laser: LaserConfig
