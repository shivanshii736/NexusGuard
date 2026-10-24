"""Hazard plug-in contract.

Every hazard turns itself into a `HazardEffect` for a given road graph. The shared
response engine (P1/P2) only ever sees the merged effect, never the hazard type.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
import networkx as nx

from ..geo import haversine_m
from ..toy_graph import edge_key

Edge = tuple[int, int]


@dataclass
class Incident:
    id: str
    kind: str                      # "flood_rescue" | "fire" | "building_collapse" | ...
    node: int
    severity: int                  # 1..3
    required_units: dict[str, int]  # service -> number of units needed
    label: str = ""
    t_start_min: float = 0.0


@dataclass
class HazardEffect:
    closed_edges: set[Edge] = field(default_factory=set)
    slowdowns: dict[Edge, float] = field(default_factory=dict)   # edge -> travel-time multiplier >= 1
    incidents: list[Incident] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    flooded_nodes: dict[int, float] = field(default_factory=dict)  # node -> water depth (m), for display

    def merge(self, other: "HazardEffect") -> "HazardEffect":
        """Closures are a union, slowdowns compound multiplicatively, incidents concatenate."""
        slow = dict(self.slowdowns)
        for e, m in other.slowdowns.items():
            slow[e] = slow.get(e, 1.0) * m
        flooded = dict(self.flooded_nodes)
        for n, d in other.flooded_nodes.items():
            flooded[n] = max(flooded.get(n, 0.0), d)
        return HazardEffect(
            closed_edges=self.closed_edges | other.closed_edges,
            slowdowns=slow,
            incidents=self.incidents + other.incidents,
            notes=self.notes + other.notes,
            flooded_nodes=flooded,
        )


def merge_effects(effects: list[HazardEffect]) -> HazardEffect:
    out = HazardEffect()
    for e in effects:
        out = out.merge(e)
    # a closed edge needs no slowdown entry
    out.slowdowns = {e: m for e, m in out.slowdowns.items() if e not in out.closed_edges}
    # the same incident reported twice (e.g. a flood that intensifies) is one incident
    uniq: dict[str, Incident] = {}
    for inc in out.incidents:
        if inc.id not in uniq or inc.severity > uniq[inc.id].severity:
            uniq[inc.id] = inc
    out.incidents = list(uniq.values())
    return out


def edge_midpoint(G: nx.Graph, e: Edge) -> tuple[float, float]:
    a, b = G.nodes[e[0]], G.nodes[e[1]]
    return (a["lat"] + b["lat"]) / 2, (a["lon"] + b["lon"]) / 2


def edges_within(G: nx.Graph, node: int, radius_m: float) -> list[Edge]:
    """Edges whose midpoint lies within radius_m of `node`."""
    n = G.nodes[node]
    out = []
    for u, v in G.edges:
        lat, lon = edge_midpoint(G, (u, v))
        if haversine_m(n["lat"], n["lon"], lat, lon) <= radius_m:
            out.append(edge_key(u, v))
    return out


def nearest_node(G: nx.Graph, lat: float, lon: float) -> int:
    return min(G.nodes, key=lambda n: haversine_m(lat, lon, G.nodes[n]["lat"], G.nodes[n]["lon"]))


class Hazard(ABC):
    """Subclass, set `type_name`, implement `apply` and `to_dict`, register in hazards/__init__."""
    type_name: str = "hazard"

    @abstractmethod
    def apply(self, G: nx.Graph) -> HazardEffect: ...

    @abstractmethod
    def params(self) -> dict: ...

    def to_dict(self) -> dict:
        return {"type": self.type_name, **self.params()}

    def describe(self) -> str:
        return self.type_name
