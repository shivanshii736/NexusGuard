"""Crew dispatch under resource contention  (P2 first deliverable).

dispatch(G, incidents, units, road_state, now, policy) assigns FREE crews to incident
needs. Competing incidents share limited crews, so someone may wait or go unserved.

Policies (both deterministic):
  "optimal"  per-service Hungarian assignment; higher severity wins scarce crews, then
             severity-weighted travel time is minimised  (default)
  "greedy"   incidents in severity order each grab the nearest free crew

Every assignment also reports `ideal_eta_s` (ETA if that incident had every crew to
itself) so `delay_s` = the cost of contention, the number the demo should show.
"""
from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from .models import Incident, RoadState, Unit
from .routing import route, travel_times_to
from .settings import ON_SCENE_S

try:
    from scipy.optimize import linear_sum_assignment
except Exception:  # scipy optional: fall back to greedy
    linear_sum_assignment = None

INF = math.inf
_BIG = 1e12
_PRIORITY = 1e6          # severity bonus dominates travel time (seconds) in the cost


@dataclass
class Assignment:
    incident_id: str
    unit_id: str
    service: str
    eta_s: float
    arrival_t: float
    ideal_eta_s: float

    @property
    def delay_s(self) -> float:
        """Extra seconds caused by competition for crews."""
        return max(0.0, self.eta_s - self.ideal_eta_s)


@dataclass
class DispatchResult:
    assignments: List[Assignment] = field(default_factory=list)
    unmet: List[Tuple[str, str]] = field(default_factory=list)   # (incident_id, service) per missing slot
    units: List[Unit] = field(default_factory=list)              # updated copies (committed crews)
    policy: str = "optimal"
    now: float = 0.0

    def to_frame(self) -> pd.DataFrame:
        cols = ["incident_id", "service", "unit_id", "eta_s", "ideal_eta_s", "delay_s", "arrival_t"]
        rows = [{"incident_id": a.incident_id, "service": a.service, "unit_id": a.unit_id,
                 "eta_s": a.eta_s, "ideal_eta_s": a.ideal_eta_s, "delay_s": a.delay_s,
                 "arrival_t": a.arrival_t} for a in self.assignments]
        rows += [{"incident_id": i, "service": s, "unit_id": None, "eta_s": INF,
                  "ideal_eta_s": INF, "delay_s": INF, "arrival_t": INF} for i, s in self.unmet]
        return pd.DataFrame(rows, columns=cols)

    def total_weighted_eta(self, incidents: Sequence[Incident]) -> float:
        sev = {i.id: i.severity for i in incidents}
        return sum(sev.get(a.incident_id, 1) * a.eta_s for a in self.assignments)

    def routes(self, G, incidents: Sequence[Incident], state: Optional[RoadState] = None) -> Dict[Tuple[str, str], list]:
        """(incident_id, unit_id) -> node path, for drawing on the Folium map."""
        inc = {i.id: i for i in incidents}
        home = {u.id: u.home_node for u in self.units}
        out = {}
        for a in self.assignments:
            _, path = route(G, home[a.unit_id], inc[a.incident_id].node, state)
            out[(a.incident_id, a.unit_id)] = path
        return out


def release_units(units: Sequence[Unit], now: float) -> List[Unit]:
    """Return crews whose job has finished to the free pool."""
    out = []
    for u in units:
        if u.busy_with is not None and u.available_at <= now:
            u = dataclasses.replace(u, busy_with=None)
        out.append(u)
    return out


def dispatch(G, incidents: Sequence[Incident], units: Sequence[Unit],
             road_state: Optional[RoadState] = None, now: float = 0.0,
             policy: str = "optimal") -> DispatchResult:
    if policy not in ("optimal", "greedy"):
        raise ValueError("policy must be 'optimal' or 'greedy'")
    use_hungarian = policy == "optimal" and linear_sum_assignment is not None

    units = release_units(units, now)
    by_id = {u.id: u for u in units}
    # one reverse search per incident: time from every node to the incident
    to_inc = {i.id: travel_times_to(G, i.node, road_state) for i in incidents}

    def eta(u: Unit, inc: Incident) -> float:
        return to_inc[inc.id].get(u.home_node, INF)

    result = DispatchResult(policy="optimal" if use_hungarian else "greedy", now=now)
    committed: Dict[str, Assignment] = {}

    services = sorted({s for i in incidents for s in i.required()})
    for svc in services:
        # slots, highest severity first (stable on time then id) -> deterministic
        order = sorted(incidents, key=lambda i: (-i.severity, i.t, i.id))
        slots: List[Tuple[Incident, int]] = []
        for inc in order:
            for k in range(inc.required().get(svc, 0)):
                slots.append((inc, k))
        if not slots:
            continue
        all_units = sorted([u for u in units if u.kind == svc], key=lambda u: u.id)
        free = [u for u in all_units if u.is_free(now)]

        # ideal ETA for slot k: k-th best among ALL crews of this kind (ignoring commitments)
        ideal = {}
        for inc in order:
            etas = sorted(eta(u, inc) for u in all_units)
            for k in range(inc.required().get(svc, 0)):
                ideal[(inc.id, k)] = etas[k] if k < len(etas) else INF

        chosen: List[Tuple[Tuple[Incident, int], Unit, float]] = []
        if free:
            M = np.array([[eta(u, inc) for u in free] for inc, _ in slots], dtype=float)
            if use_hungarian:
                sev = np.array([inc.severity for inc, _ in slots], dtype=float)[:, None]
                cost = np.where(np.isfinite(M), sev * (M - _PRIORITY), _BIG)
                rows, cols = linear_sum_assignment(cost)
                for r, c in zip(rows, cols):
                    if np.isfinite(M[r, c]):
                        chosen.append((slots[r], free[c], float(M[r, c])))
            else:
                taken: set = set()
                for r, slot in enumerate(slots):
                    best = None
                    for c, u in enumerate(free):
                        if c in taken or not np.isfinite(M[r, c]):
                            continue
                        if best is None or (M[r, c], u.id) < (M[r, best], free[best].id):
                            best = c
                    if best is not None:
                        taken.add(best)
                        chosen.append((slot, free[best], float(M[r, best])))

        served = set()
        for (inc, k), u, t in chosen:
            a = Assignment(inc.id, u.id, svc, t, now + t, ideal[(inc.id, k)])
            result.assignments.append(a)
            served.add((inc.id, k))
            busy_until = now + 2 * t + ON_SCENE_S.get(svc, 1800)
            by_id[u.id] = dataclasses.replace(u, available_at=busy_until, busy_with=inc.id)
        for inc, k in slots:
            if (inc.id, k) not in served:
                result.unmet.append((inc.id, svc))

    result.units = [by_id[u.id] for u in units]
    result.assignments.sort(key=lambda a: (a.incident_id, a.service, a.unit_id))
    return result
