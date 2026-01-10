import sys
import os
from unittest.mock import MagicMock

# Mock GTK and other heavy dependencies
sys.modules["gi"] = MagicMock()
sys.modules["gi.repository"] = MagicMock()
sys.modules["gi.repository.Gtk"] = MagicMock()
sys.modules["gi.repository.Adw"] = MagicMock()
sys.modules["gi.repository.Gdk"] = MagicMock()
sys.modules["gi.repository.GLib"] = MagicMock()
sys.modules["pluggy"] = MagicMock()
sys.modules["pyclipper"] = MagicMock()
sys.modules["cairo"] = MagicMock()
sys.modules["pyvips"] = MagicMock()
sys.modules["vtracer"] = MagicMock()
sys.modules["ezdxf"] = MagicMock()
sys.modules["blinker"] = MagicMock()
sys.modules["scipy"] = MagicMock()
sys.modules["scipy.optimize"] = MagicMock()
sys.modules["pydantic"] = MagicMock()

# Mock internal app imports that might fail in this env
sys.modules["rayforge.core.hooks"] = MagicMock()
sys.modules["rayforge.core.package_manager"] = MagicMock()
sys.modules["rayforge.ui_gtk.icons"] = MagicMock()

# Mock gettext
import builtins
builtins._ = lambda x: x

# Add apps/desktop to path
apps_dir = os.path.abspath("apps/desktop")
sys.path.append(apps_dir)
# Add packages/core/src to path for core imports
core_dir = os.path.abspath("packages/core/src")
sys.path.append(core_dir)

import rayforge.context
from rayforge.context import RayforgeContext

def test_init():
    ctx = RayforgeContext()
    # Mock CONFIG_DIR and others in config.py if needed, 
    # but initialize_full_context will try to import .config
    
    # Let's mock the .config module
    config_mock = MagicMock()
    config_mock.CONFIG_DIR = "/tmp/rayforge_test_config"
    config_mock.MACHINE_DIR = "/tmp/rayforge_test_config/machines"
    config_mock.CONFIG_FILE = "/tmp/rayforge_test_config/config.yaml"
    sys.modules["rayforge.config"] = config_mock
    
    try:
        ctx.initialize_full_context()
        print("Successfully initialized context with SettingsManager")
        print(f"SettingsManager: {ctx.settings_mgr}")
    except Exception as e:
        print(f"Failed to initialize context: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_init()
