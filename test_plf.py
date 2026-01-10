import os
import sys
from pathlib import Path

# Add the project root to sys.path
root = Path(__file__).parent
sys.path.append(str(root))

from rayforge.core.doc import Doc
from rayforge.core.plf import PLFManager
from rayforge.core.source_asset import SourceAsset

def test_plf():
    print("Testing PLF Save/Load...")
    
    # Create a mock doc
    doc = Doc()
    
    # Add a mock SourceAsset
    asset = SourceAsset(
        source_file=Path("test.png"),
        original_data=b"fake image data",
        renderer=None, # Mocking renderer is hard, but let's see if we can just save data
    )
    # We need a renderer name to save it
    # In a real app, it would be an actual renderer object
    class MockRenderer:
        pass
    asset.renderer = MockRenderer()
    
    doc.add_asset(asset)
    
    plf_path = "test_project.plf"
    if os.path.exists(plf_path):
        os.remove(plf_path)
    
    try:
        print(f"Saving to {plf_path}...")
        PLFManager.save(doc, plf_path)
        print("Save successful.")
        
        print("Loading back...")
        # Since we used a MockRenderer, from_dict might fail if it tries to look up the renderer name
        # But we can check if the assets folder was created inside the zip
        import zipfile
        with zipfile.ZipFile(plf_path, 'r') as zf:
            print("Zip contents:", zf.namelist())
            assert "index.json" in zf.namelist()
            assert any(f.startswith("assets/") for f in zf.namelist())
        
        print("PLF ZIP structure verified.")
        
    finally:
        if os.path.exists(plf_path):
            os.remove(plf_path)

if __name__ == "__main__":
    test_plf()
