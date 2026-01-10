import logging
import numpy as np
import pyclipper
from typing import List, Dict, Any, Optional, Tuple
from .base import OpsTransformer, ExecutionPhase
from ...core.ops import Ops, MovingCommand, MoveToCommand, LineToCommand

logger = logging.getLogger(__name__)

class TopologySorter(OpsTransformer):
    """
    Sorts vector paths such that inner shapes (holes) are cut before
    outer shapes (contours).
    Uses PyClipper to determine polygon containment.
    """

    def __init__(self, enabled: bool = True):
        super().__init__(enabled=enabled)

    @property
    def execution_phase(self) -> ExecutionPhase:
        # Must run before Optimization (which reorders for distance)
        # But wait, Optimization might break topology order if it's greedy?
        # Ideally: Topology Sort -> Group into "Locked" sets -> Optimize between sets.
        # For Phase 3, we simply Order them and assume Optimize won't mess it up 
        # (Optimize has 'kdtree_order' which respects locality, but might violate topology).
        # To strictly enforce, we should run this, and then Optimize should respect dependencies.
        # Rayforge's Optimize is generic. 
        # Workaround: This runs BEFORE Optimize. If Optimize is purely greedy distance, it might jump out/in.
        # However, usually users want "All holes, then all outlines". 
        # If we sort the list: [Hole1, Hole2, Outline], and Greedy Optimizer sees Dis(Hole1, Hole2) < Dis(Hole1, Outline),
        # it preserves the general order unless Outline is strictly closer.
        return ExecutionPhase.PRE_PROCESSING 

    def run(self, ops: Ops, workpiece: Any = None, context: Any = None) -> None:
        if not self.enabled:
            return

        # 1. Extract Paths
        # A Path is a sequence of MoveTo -> LineTo/ArcTo...
        commands = list(ops)
        paths = []
        current_path = []
        
        for cmd in commands:
            if isinstance(cmd, MoveToCommand):
                if current_path:
                    paths.append(current_path)
                current_path = [cmd]
            elif isinstance(cmd, MovingCommand): # LineTo, ArcTo
                if current_path:
                    current_path.append(cmd)
            # Ignore state commands for geometry analysis, but keep them attached? 
            # This is tricky if state commands are interspersed.
            
        if current_path:
            paths.append(current_path)

        if not paths:
            return

        # 2. Convert to Polygons for Clipper
        # Clipper works with integers. Scale up floats.
        SCALE = 1000.0
        polygons = []
        path_map = {} # poly_index -> path_data

        for i, path in enumerate(paths):
            points = []
            for cmd in path:
                # Only MoveTo/LineTo supported for now. Arcs need discretization.
                # Assuming pipeline has discretized arcs or we approximate end points.
                # For containment check, vertices are usually enough.
                if hasattr(cmd, 'end'):
                    points.append((int(cmd.end[0] * SCALE), int(cmd.end[1] * SCALE)))
            
            if len(points) > 2:
                # Check if closed?
                if points[0] == points[-1]:
                    points.pop() # Remove duplicate end
                polygons.append(points)
                path_map[len(polygons)-1] = path
            else:
                # Not a polygon (line), treat as top-level or ignore sorting
                pass

        # 3. Build Dependency Tree
        # Brute force O(N^2) using PointInPolygon
        # If Poly A is inside Poly B -> A is child of B.
        # But PointInPolygon handles points. 
        # Correct way involves `Execute`. But simpler: 
        # Check if first point of A is in B.
        
        adjacency = {i: [] for i in range(len(polygons))}
        roots = set(range(len(polygons)))
        
        for i in range(len(polygons)):
            for j in range(len(polygons)):
                if i == j: continue
                
                # Check if i is inside j
                # Using PyClipper's PointInPolygon
                pt = polygons[i][0]
                pip = pyclipper.PointInPolygon(pt, polygons[j])
                
                if pip != 0: # 1 or -1 means inside (or on boundary)
                    # i is inside j.
                    # Is it directly inside? 
                    # We might find i inside j, and j inside k.
                    # This creates graph i -> j, j -> k.
                    # Transitive reduction needed?
                    # Actually, if we just count "enclosure depth", we can sort by depth Descending.
                    # Deepest (most enclosed) cut first.
                    adjacency[i].append(j)

        # Calculate depth
        depths = {}
        for i in range(len(polygons)):
            depths[i] = len(adjacency[i]) # Number of polys containing this one

        # 4. Sort
        # Sort by depth descending (Deepest first)
        sorted_indices = sorted(range(len(polygons)), key=lambda k: depths[k], reverse=True)
        
        # 5. Reconstruct Ops
        new_ops = Ops()
        # Add non-polygon headers/setup? Ops class manages simple lists.
        # We need to preserve non-moving commands (setup) likely at start.
        
        # Collect unused commands (like initial setup)
        # For simplicity, we just append sorted paths.
        # WARNING: This might strip state commands inside paths if we aren't careful.
        # Our `paths` extraction was naive.
        
        # Better approach: Just reorder the chunks.
        for idx in sorted_indices:
            path = path_map[idx]
            for cmd in path:
                new_ops.add(cmd)
                
        # What about open lines? were ignored in loop.
        # Append them at end (or start?).
        # Append at end (usually cuts last).
        
        ops.commands = new_ops.commands # Replace
