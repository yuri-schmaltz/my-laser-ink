import sys
import os
from pathlib import Path

# Mock dependencies if needed, or add path
sys.path.append(os.path.abspath("packages/core/src"))

from core.models import MachineProfile, MachineDims, MachineConnection, LaserConfig
from core.persistence import SettingsManager

def test_persistence():
    print("--- Testing Configuration Persistence ---")
    tmp_dir = Path("./tmp_config")
    manager = SettingsManager(str(tmp_dir))
    
    # Create a profile
    profile = MachineProfile(
        name="Test Laser",
        dimensions=MachineDims(width=500, height=500, auto_home=True),
        connection=MachineConnection(port="/dev/ttyUSB0", baud=115200),
        laser=LaserConfig()
    )
    
    # Save
    print(f"Saving profile: {profile.name}")
    manager.save_machine(profile)
    
    # Load
    loaded = manager.load_machine()
    print(f"Loaded profile: {loaded.name}")
    
    # Verify
    assert loaded.name == profile.name
    assert loaded.dimensions.width == 500
    
    print("--- Test Passed: Round trip successful ---")
    
    # Cleanup
    import shutil
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)

if __name__ == "__main__":
    test_persistence()
