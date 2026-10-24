"""Flood plug-in: rainfall -> water level -> per-edge depth -> closures / slowdowns.

Model (all thresholds are labelled assumptions, tweak in the sidebar / constructor):
  water_level_m = max(0, rainfall - drainage) * duration_h * RUNOFF_M_PER_MM
  depth(edge)   = max(0, water_level_m - lowest endpoint elevation)
  depth >= close_depth_m            -> edge closed
  slow_depth_m <= depth < close     -> travel time x (1 + 2 * depth/close)   (max x3)
Underpasses use a lower closure threshold (they pond first).
"""
from __future__ import annotations
import networkx as nx

from .base import Hazard, HazardEffect, Incident
from ..toy_graph import edge_key

RUNOFF_M_PER_MM = 0.01


class FloodHazard(Hazard):
    type_name = "flood"

    def __init__(self, rainfall_mm_hr: float = 50, duration_h: float = 2, drainage_mm_hr: float = 20,
                 close_depth_m: float = 0.30, slow_depth_m: float = 0.10,
                 underpass_close_depth_m: float = 0.15, rescue_calls: int = 1):
        self.rainfall_mm_hr = rainfall_mm_hr
        self.duration_h = duration_h
        self.drainage_mm_hr = drainage_mm_hr
        self.close_depth_m = close_depth_m
        self.slow_depth_m = slow_depth_m
        self.underpass_close_depth_m = underpass_close_depth_m
        self.rescue_calls = rescue_calls

    @property
    def water_level_m(self) -> float:
        return max(0.0, self.rainfall_mm_hr - self.drainage_mm_hr) * self.duration_h * RUNOFF_M_PER_MM

    def node_depth(self, G: nx.Graph, n: int) -> float:
        return max(0.0, self.water_level_m - G.nodes[n]["elevation"])

    def apply(self, G: nx.Graph) -> HazardEffect:
        eff = HazardEffect()
        level = self.water_level_m
        if level <= 0:
            eff.notes.append("Flood: drainage keeps up with rainfall, no inundation.")
            return eff

        eff.flooded_nodes = {n: round(self.node_depth(G, n), 2) for n in G.nodes if self.node_depth(G, n) > 0}
        for u, v, d in G.edges(data=True):
            depth = max(0.0, level - min(G.nodes[u]["elevation"], G.nodes[v]["elevation"]))
            close_at = self.underpass_close_depth_m if d.get("underpass") else self.close_depth_m
            e = edge_key(u, v)
            if depth >= close_at:
                eff.closed_edges.add(e)
            elif depth >= self.slow_depth_m:
                eff.slowdowns[e] = 1 + 2 * depth / self.close_depth_m

        # stranded-people rescue calls at the deepest nodes
        deepest = sorted(G.nodes, key=lambda n: -self.node_depth(G, n))[: self.rescue_calls]
        for i, n in enumerate(deepest, 1):
            if self.node_depth(G, n) > 0:
                eff.incidents.append(Incident(
                    id=f"FLOOD-{n}", kind="flood_rescue", node=n, severity=2,
                    required_units={"rescue": 1, "ambulance": 1},
                    label=f"Stranded residents at {G.nodes[n]['label']} ({self.node_depth(G, n):.2f} m water)",
                ))
        eff.notes.append(f"Flood: water level {level:.2f} m, {len(eff.closed_edges)} roads closed, "
                         f"{len(eff.slowdowns)} slowed.")
        return eff

    def params(self) -> dict:
        return dict(rainfall_mm_hr=self.rainfall_mm_hr, duration_h=self.duration_h,
                    drainage_mm_hr=self.drainage_mm_hr, close_depth_m=self.close_depth_m,
                    slow_depth_m=self.slow_depth_m, underpass_close_depth_m=self.underpass_close_depth_m,
                    rescue_calls=self.rescue_calls)

    def describe(self) -> str:
        return f"Flood {self.rainfall_mm_hr:g} mm/hr x {self.duration_h:g} h"
