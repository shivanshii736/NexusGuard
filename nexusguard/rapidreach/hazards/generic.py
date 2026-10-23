"""Generic incident plug-in: collapses, lake breaches, anything placed manually.

The location can be a graph node or a lat/lon (snapped to the nearest node), which is
what lets the deck claim "other hazards through generic incident placement".
"""
from __future__ import annotations
import networkx as nx

from .base import Hazard, HazardEffect, Incident, edges_within, nearest_node

# kind -> (closure radius m, slowdown radius m, slowdown multiplier, default units)
GENERIC_PRESETS = {
    "building_collapse": (350, 700, 1.6, {"rescue": 2, "ambulance": 2, "fire": 1}),
    "lake_breach":       (900, 1300, 2.0, {"rescue": 2, "ambulance": 1}),
    "road_accident":     (0, 350, 1.4, {"ambulance": 1}),
    "other":             (0, 0, 1.0, {"ambulance": 1}),
}


class GenericIncident(Hazard):
    type_name = "generic"

    def __init__(self, kind: str = "other", node: int | None = None, lat: float | None = None,
                 lon: float | None = None, severity: int = 2, closure_radius_m: float | None = None,
                 required_units: dict[str, int] | None = None, label: str = ""):
        if kind not in GENERIC_PRESETS:
            raise ValueError(f"unknown generic kind {kind!r}; choose from {sorted(GENERIC_PRESETS)}")
        if node is None and (lat is None or lon is None):
            raise ValueError("give either node or lat+lon")
        self.kind, self.node, self.lat, self.lon = kind, node, lat, lon
        self.severity, self.closure_radius_m = severity, closure_radius_m
        self.required_units, self.label = required_units, label

    def apply(self, G: nx.Graph) -> HazardEffect:
        node = self.node if self.node is not None else nearest_node(G, self.lat, self.lon)
        close_r, slow_r, mult, units = GENERIC_PRESETS[self.kind]
        if self.closure_radius_m is not None:
            close_r = self.closure_radius_m
            slow_r = max(slow_r, close_r * 1.5)
        eff = HazardEffect()
        closed = set(edges_within(G, node, close_r)) if close_r else set()
        eff.closed_edges |= closed
        if slow_r:
            for e in edges_within(G, node, slow_r):
                if e not in closed:
                    eff.slowdowns[e] = mult
        where = G.nodes[node]["label"]
        eff.incidents.append(Incident(
            id=f"{self.kind.upper()}-{node}", kind=self.kind, node=node, severity=self.severity,
            required_units=dict(self.required_units or units),
            label=self.label or f"{self.kind.replace('_', ' ').title()} at {where}"))
        eff.notes.append(f"{self.kind} at {where}: {len(closed)} roads closed.")
        return eff

    def params(self) -> dict:
        return dict(kind=self.kind, node=self.node, lat=self.lat, lon=self.lon, severity=self.severity,
                    closure_radius_m=self.closure_radius_m, required_units=self.required_units, label=self.label)

    def describe(self) -> str:
        return f"{self.kind} @ {self.node if self.node is not None else (self.lat, self.lon)}"
