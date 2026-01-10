import numpy as np
import logging
from typing import Optional, Dict, Any, Tuple
from ...core.ops import Ops, SectionType, ScanLinePowerCommand, MoveToCommand
from ..artifact import WorkPieceArtifact
from ..coord import CoordinateSystem
from .base import OpsProducer

logger = logging.getLogger(__name__)

class AdvancedRasterizer(OpsProducer):
    """
    Advanced Rasterizer supporting:
    1. Threshold (Standard B&W)
    2. Dithering (Floyd-Steinberg) for pseudo-grayscale on 1-bit lasers.
    3. Grayscale (Power Mapping) for lasers supporting variable power (M4).
    """

    def __init__(self, mode: str = "threshold", threshold: int = 128, resolution_check: bool = False):
        """
        mode: "threshold", "dither", "grayscale"
        """
        super().__init__()
        self.mode = mode
        self.threshold = threshold
        self.resolution_check = resolution_check

    def _apply_threshold(self, image: np.ndarray) -> np.ndarray:
        return (image < self.threshold).astype(np.uint8) * 255

    def _apply_dither(self, image: np.ndarray) -> np.ndarray:
        """
        Floyd-Steinberg dithering.
        image: 2D numpy array (float or int), 0-255.
        Returns: 2D numpy array (0 or 255).
        """
        h, w = image.shape
        dithered = image.astype(float)
        
        for y in range(h):
            for x in range(w):
                old_pixel = dithered[y, x]
                new_pixel = 255 if old_pixel > 127 else 0 # Threshold at 50%
                dithered[y, x] = new_pixel
                quant_error = old_pixel - new_pixel
                
                # Distribute error
                if x + 1 < w:
                    dithered[y, x + 1] += quant_error * 7 / 16
                if y + 1 < h:
                    if x > 0:
                        dithered[y + 1, x - 1] += quant_error * 3 / 16
                    dithered[y + 1, x] += quant_error * 5 / 16
                    if x + 1 < w:
                        dithered[y + 1, x + 1] += quant_error * 1 / 16
                        
        # Invert color logic: In laser, 0 (Black) is ON (Burn), 255 (White) is OFF.
        # But image is usually 0=Black.
        # Let's assume input image 0=Black, 255=White.
        # We want "Burn" where it is Black.
        # So output: 1 (Burn) if dithered < 128 (Black), 0 (Skip) if dithered > 128 (White).
        return (dithered < 128).astype(np.uint8) * 255

    def _apply_grayscale(self, image: np.ndarray) -> np.ndarray:
        """
        Maps pixel intensity to power.
        Input: 0 (Black) - 255 (White).
        Output: 255 (Max Power) - 0 (Min Power).
        """
        return 255 - image

    def run(
        self,
        laser: Any,
        surface,
        pixels_per_mm: Tuple[float, float],
        *,
        workpiece: Any = None,
        settings: Optional[Dict[str, Any]] = None,
        y_offset_mm: float = 0.0,
        proxy: Any = None,
    ) -> WorkPieceArtifact:
        if workpiece is None:
            raise ValueError("Workpiece required")

        # 1. Prepare Image
        width = surface.get_width()
        height = surface.get_height()
        raw_data = np.frombuffer(surface.get_data(), dtype=np.uint8).reshape((height, width, 4))
        
        # Extract Blue/Green/Red (Cairo is BGRA or ARGB depending on endian, usually BGRA)
        # Using standard luminosity formula
        b, g, r = raw_data[:,:,0], raw_data[:,:,1], raw_data[:,:,2]
        grayscale_img = 0.299 * r + 0.587 * g + 0.114 * b
        
        # 2. Process based on mode
        if self.mode == "dither":
            processed = self._apply_dither(grayscale_img)
            use_variable_power = False
        elif self.mode == "grayscale":
            processed = self._apply_grayscale(grayscale_img).astype(np.uint8)
            use_variable_power = True # Each pixel has its own power
        else: # threshold
            processed = self._apply_threshold(grayscale_img)
            use_variable_power = False

        # 3. Generate Ops
        ops = Ops()
        ops.ops_section_start(SectionType.RASTER_FILL, workpiece.uid)
        
        # Basic Horizontal Scanning
        y_res_mm = 1.0 / pixels_per_mm[1]
        x_res_mm = 1.0 / pixels_per_mm[0]
        
        for y in range(height):
            row = processed[y]
            if not np.any(row): 
                continue # Skip empty rows
                
            y_pos = y * y_res_mm + y_offset_mm
            
            # Identify segments or scanlines
            if use_variable_power:
                # ScanLinePowerCommand treats a whole line as a sequence of power values
                # We need to find the start and end of non-zero data to avoid scanning empty space
                non_zero = np.where(row > 0)[0]
                if non_zero.size == 0: continue
                
                start_x_idx = non_zero[0]
                end_x_idx = non_zero[-1]
                
                start_x_mm = start_x_idx * x_res_mm
                end_x_mm = (end_x_idx + 1) * x_res_mm
                
                # Extract power values for the active segment
                power_values = row[start_x_idx : end_x_idx + 1].tobytes()
                
                # Move to start
                ops.add(MoveToCommand((start_x_mm, y_pos)))
                # Scan line
                ops.add(ScanLinePowerCommand((end_x_mm, y_pos), power_values=power_values))
                
            else:
                # Binary (Threshold/Dither): 255=Burn, 0=Skip.
                # Find segments of 255
                diffs = np.diff(np.hstack(([0], row, [0])))
                starts = np.where(diffs == 255)[0] # 0 -> 255 rising edge? No, if row is 0/255.
                # Wait, my _apply_threshold output 255 for Burn.
                # So 0->255 is rising edge (+255), 255->0 is falling (-255).
                
                # Actually, simple way:
                # row is 0 or 255.
                # logical:
                is_on = row == 255
                # ranges
                # ... standard run-length encoding logic ...
                # Reusing numpy logic for speed
                padded = np.concatenate(([0], is_on.astype(int), [0]))
                changes = np.diff(padded)
                starts = np.where(changes == 1)[0]
                ends = np.where(changes == -1)[0]
                
                for s, e in zip(starts, ends):
                    start_mm = s * x_res_mm
                    end_mm = e * x_res_mm
                    
                    ops.move_to(start_mm, y_pos)
                    # Use max power matching 255 intensity
                    ops.line_to(end_mm, y_pos)

        ops.ops_section_end(SectionType.RASTER_FILL)
        
        return WorkPieceArtifact(
            ops=ops,
            is_scalable=False,
            source_coordinate_system=CoordinateSystem.MILLIMETER_SPACE,
            generation_size=workpiece.size,
        )

    def is_vector_producer(self) -> bool:
        return False
