import json
import logging
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, Any, Optional

from .doc import Doc
from .source_asset import SourceAsset

logger = logging.getLogger(__name__)

class PLFManager:
    """
    Manages the Portable Laser Format (.plf), a container format for Rayforge projects.
    A PLF file is a ZIP archive containing:
    - index.json: The document structure and metadata.
    - assets/: A folder containing binary data for SourceAssets.
    - preview.png: (Optional) A thumbnail of the project.
    """

    @staticmethod
    def save(doc: Doc, file_path: str):
        """Saves a Document to a .plf file."""
        temp_dir = tempfile.mkdtemp()
        try:
            index_path = os.path.join(temp_dir, "index.json")
            assets_dir = os.path.join(temp_dir, "assets")
            os.makedirs(assets_dir, exist_ok=True)

            doc_dict = doc.to_dict()
            
            # Extract large binary data from SourceAssets to separate files
            for asset_data in doc_dict.get("assets", []):
                if asset_data.get("type") == "source":
                    uid = asset_data["uid"]
                    original_data = asset_data.get("original_data")
                    
                    if original_data and isinstance(original_data, bytes):
                        # Determine a suitable filename extension
                        source_file = asset_data.get("source_file", "")
                        ext = os.path.splitext(source_file)[1] or ".bin"
                        asset_filename = f"{uid}{ext}"
                        
                        asset_path = os.path.join(assets_dir, asset_filename)
                        with open(asset_path, "wb") as f:
                            f.write(original_data)
                        
                        # Replace binary data with a path reference in the JSON
                        asset_data["plf_asset_path"] = f"assets/{asset_filename}"
                        del asset_data["original_data"]
                        
                        # We also might want to strip base_render_data as it can be regenerated
                        if "base_render_data" in asset_data:
                            del asset_data["base_render_data"]

            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(doc_dict, f, indent=2)

            # Create the ZIP
            with zipfile.ZipFile(file_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, temp_dir)
                        zf.write(full_path, rel_path)
            
            logger.info(f"Successfully saved PLF to {file_path}")

        finally:
            shutil.rmtree(temp_dir)

    @staticmethod
    def load(file_path: str) -> Doc:
        """Loads a Document from a .plf file."""
        temp_dir = tempfile.mkdtemp()
        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                zf.extractall(temp_dir)
            
            index_path = os.path.join(temp_dir, "index.json")
            if not os.path.exists(index_path):
                raise FileNotFoundError("PLF archive is missing index.json")
            
            with open(index_path, "r", encoding="utf-8") as f:
                doc_dict = json.load(f)
            
            # Reinject binary data from assets folder
            for asset_data in doc_dict.get("assets", []):
                rel_path = asset_data.get("plf_asset_path")
                if rel_path:
                    abs_path = os.path.join(temp_dir, rel_path)
                    if os.path.exists(abs_path):
                        with open(abs_path, "rb") as f:
                            asset_data["original_data"] = f.read()
                    else:
                        logger.warning(f"Asset file not found in PLF: {rel_path}")

            return Doc.from_dict(doc_dict)

        finally:
            shutil.rmtree(temp_dir)
