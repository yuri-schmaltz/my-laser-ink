import yaml
import os
from typing import Optional
from pathlib import Path
from .models import MachineProfile, MaterialLibrary

class SettingsManager:
    def __init__(self, config_dir: str):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.machines_file = self.config_dir / "machines.yaml"
        self.materials_file = self.config_dir / "materials.yaml"

    def save_machine(self, profile: MachineProfile):
        # We might want to support multiple machines. 
        # For simplicity MVP, just saving one or a list. 
        # Let's save a list of dicts for now to be scalable, but the method takes one to save/update.
        # Implementation Detail: Overwriting the file with the single profile for this demo.
        data = profile.model_dump()
        with open(self.machines_file, 'w') as f:
            yaml.dump(data, f)

    def load_machine(self) -> Optional[MachineProfile]:
        if not self.machines_file.exists():
            return None
        with open(self.machines_file, 'r') as f:
            data = yaml.safe_load(f)
        return MachineProfile(**data)

    def save_materials(self, libra: MaterialLibrary):
        data = libra.model_dump()
        with open(self.materials_file, 'w') as f:
            yaml.dump(data, f)

    def load_materials(self) -> Optional[MaterialLibrary]:
        if not self.materials_file.exists():
            return None
        with open(self.materials_file, 'r') as f:
            data = yaml.safe_load(f)
        return MaterialLibrary(**data)
