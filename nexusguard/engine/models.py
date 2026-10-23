"""P2 engine data models.

PROPOSED contract: these mirror what the engine needs from nexusguard/types.py.
Once the team's types.py is agreed, either re-export these from there or adapt
the field names here. The engine only relies on the attributes listed below.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Hashable, Mapping, Tuple

Node = Hashable
Edge = Tuple[Node, Node]

SERVICES = ("ambulance", "fire", "rescue")

# Which services an incident kind pulls in by default (override via Incident.needs).
DEFAULT_NEEDS: Dict[str, Dict[str, int]] = {
    "fire": {"fire": 1, "ambulance": 1},
    "flood": {"rescue": 1, "ambulance": 1},
    "generic": {"rescue": 1, "ambulance": 1},
    "medical": {"ambulance": 1},
}


@dataclass(frozen=True)
class Ward:
    id: str
    name: str
    centroid: Node                      # graph node that represents the ward
    nodes: Tuple[Node, ...] = ()        # optional: all graph nodes inside the ward
    population: float = 1.0             # weight for coverage (1.0 = unweighted)


@dataclass(frozen=True)
class Station:
    id: str
    name: str
    kind: str                           # one of SERVICES
    node: Node
    units: int = 1


@dataclass
class Unit:
    id: str
    kind: str                           # one of SERVICES
    home_node: Node                     # where it sits when free (base or staging site)
    available_at: float = 0.0           # seconds; free when available_at <= now
    busy_with: str | None = None        # incident id while committed

    def is_free(self, now: float) -> bool:
        return self.available_at <= now


@dataclass(frozen=True)
class Incident:
    id: str
    kind: str                           # fire | flood | generic | medical
    node: Node
    severity: int = 1                   # 1 (low) .. 5 (critical); drives priority
    needs: Mapping[str, int] | None = None
    t: float = 0.0                      # seconds, time of occurrence

    def required(self) -> Dict[str, int]:
        if self.needs is not None:
            return dict(self.needs)
        return dict(DEFAULT_NEEDS.get(self.kind, DEFAULT_NEEDS["generic"]))


@dataclass(frozen=True)
class RoadState:
    """Output of the hazard modules: which directed edges are closed / slowed."""
    closed: FrozenSet[Edge] = frozenset()
    slow: Mapping[Edge, float] = field(default_factory=dict)   # edge -> multiplier >= 1

    @staticmethod
    def merge(*states: "RoadState") -> "RoadState":
        """Combine several hazards (flood + collapse + ...): union of closures, max slowdown."""
        closed: set = set()
        slow: Dict[Edge, float] = {}
        for s in states:
            closed |= set(s.closed)
            for e, m in s.slow.items():
                slow[e] = max(slow.get(e, 1.0), m)
        return RoadState(frozenset(closed), slow)


def units_from_stations(stations) -> list:
    """Expand stations into individual crews (one Unit per vehicle)."""
    units = []
    for st in stations:
        for i in range(max(1, int(st.units))):
            units.append(Unit(id=f"{st.id}-{i + 1}", kind=st.kind, home_node=st.node))
    return units
