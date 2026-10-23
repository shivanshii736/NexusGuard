"""Fire plug-in: one incident location plus a closure / smoke-slowdown footprint.

severity 1: small fire, adjacent roads slowed (hose lines, crowding)
severity 2: adjacent roads closed, nearby roads slowed
severity 3: wider closure, wider slowdown, needs more engines
Radii are assumptions (metres to edge midpoints).
"""
from __future__ import annotations
import networkx as nx

from .base import Hazard, HazardEffect, Incident, edges_within

# severity -> (closure radius m, slowdown radius m, slowdown multiplier, units needed)
FIRE_PROFILE = {
    1: (0, 400, 1.5, {"fire": 1}),
    2: (350, 700, 1.8, {"fire": 2, "ambulance": 1}),
    3: (700, 1000, 2.0, {"fire": 3, "ambulance": 2, "rescue": 1}),
}


class FireHazard(Hazard):
    type_name = "fire"

    def __init__(self, node: int, severity: int = 2, label: str = ""):
        if severity not in FIRE_PROFILE:
            raise ValueError("fire severity must be 1, 2 or 3")
        self.node, self.severity, self.label = node, severity, label

    def apply(self, G: nx.Graph) -> HazardEffect:
        close_r, slow_r, mult, units = FIRE_PROFILE[self.severity]
        eff = HazardEffect()
        closed = set(edges_within(G, self.node, close_r)) if close_r else set()
        eff.closed_edges |= closed
        for e in edges_within(G, self.node, slow_r):
            if e not in closed:
                eff.slowdowns[e] = mult
        where = G.nodes[self.node]["label"]
        eff.incidents.append(Incident(
            id=f"FIRE-{self.node}", kind="fire", node=self.node, severity=self.severity,
            required_units=dict(units), label=self.label or f"Fire (sev {self.severity}) at {where}"))
        eff.notes.append(f"Fire at {where}: {len(closed)} roads closed, {len(eff.slowdowns)} slowed.")
        return eff

    def params(self) -> dict:
        return dict(node=self.node, severity=self.severity, label=self.label)

    def describe(self) -> str:
        return f"Fire sev {self.severity} @ node {self.node}"
