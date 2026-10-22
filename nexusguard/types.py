"""SHARED CONTRACT. Change only after all three of you agree (it breaks everyone).

Graph convention: networkx.MultiDiGraph (osmnx-compatible). Each edge has
  length (m), travel_time (s, free-flow), peak_time (s, with ASSUMED multipliers).
Each node has x (lon) and y (lat). An edge id is the tuple (u, v, key).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, Optional

Kind = Literal["ambulance", "fire", "rescue"]
EdgeId = tuple  # (u, v, key)


@dataclass(frozen=True)
class Asset:
    """A response base with a number of crews/vehicles."""
    id: str
    kind: Kind
    node: int            # nearest graph node
    name: str = ""
    crews: int = 1
    is_proxy: bool = False   # True when location is a stand-in (e.g. hospital for ambulance base)


@dataclass(frozen=True)
class Zone:
    """A ward (or grid cell fallback) represented by one graph node."""
    id: str
    name: str
    node: int
    population: Optional[float] = None


@dataclass
class Incident:
    id: str
    kind: str            # "fire", "flood", "collapse", "lake_breach", "other"
    node: int
    severity: int = 1    # 1..3
    needs: dict = field(default_factory=lambda: {"ambulance": 1})  # Kind -> crews required
    t_start_min: float = 0.0


@dataclass
class RoadState:
    """What the hazards did to the road graph. Produced by hazards/, consumed by engine/."""
    closed_edges: set = field(default_factory=set)       # set[EdgeId]
    slowdown: dict = field(default_factory=dict)         # EdgeId -> time multiplier >= 1.0
    incidents: list = field(default_factory=list)        # list[Incident]
    notes: list = field(default_factory=list)            # human-readable provenance

    def merge(self, other: "RoadState") -> "RoadState":
        slow = dict(self.slowdown)
        for e, f in other.slowdown.items():
            slow[e] = max(slow.get(e, 1.0), f)
        return RoadState(self.closed_edges | other.closed_edges, slow,
                         self.incidents + other.incidents, self.notes + other.notes)


@dataclass
class Assignment:
    incident_id: str
    kind: Kind
    asset_id: Optional[str]      # None => no free crew / unreachable
    eta_s: Optional[float]
    breach: bool                 # eta > target (or unassigned)


@dataclass
class CoverageReport:
    """Zone-level coverage for one kind under one RoadState / crew availability."""
    kind: Kind
    target_s: float
    eta_by_zone: dict            # zone_id -> seconds (inf if unreachable)
    covered_zone_ids: set
    pct_zones: float
    pct_population: Optional[float] = None


@dataclass
class Intervention:
    kind: Kind
    staging_nodes: list          # nodes where extra vehicles are pre-positioned
    before: CoverageReport
    after: CoverageReport


@dataclass
class Alert:
    level: Literal["info", "warn", "critical"]
    message: str
    zone_id: Optional[str] = None
    incident_id: Optional[str] = None
