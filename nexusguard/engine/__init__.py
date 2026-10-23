"""P2 response engine: ETAs, coverage, dispatch under contention, pre-positioning, alerts.

Typical use (P3's app.py):

    from nexusguard.engine import EngineSession
    session = EngineSession(G, wards, stations)         # computes the baseline once
    snap = session.update(road_state, incidents, now=0) # Live Mode: hazards changed
    plan = session.preposition(road_state=road_state)   # recommendations + before/after
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import pandas as pd

from .alerts import Alert, AlertEngine
from .coverage import (coverage_summary, compare_coverage, compute_coverage,
                       providers_from_stations, providers_from_units)
from .dispatch import Assignment, DispatchResult, dispatch, release_units
from .models import (DEFAULT_NEEDS, SERVICES, Incident, RoadState, Station, Unit, Ward,
                     units_from_stations)
from .optimizer import PrepositionPlan, apply_plan, rank_staging_sites, recommend_prepositioning
from .routing import eta, isolated_nodes, multi_source_times, route, travel_times_from, travel_times_to
from .settings import get_targets_s


@dataclass
class Snapshot:
    coverage: pd.DataFrame
    summary: pd.DataFrame
    dispatch: Optional[DispatchResult]
    alerts: List[Alert] = field(default_factory=list)


class EngineSession:
    """Stateful facade: baseline once, then cheap updates as hazards/incidents change."""

    def __init__(self, G, wards: Sequence[Ward], stations: Sequence[Station],
                 targets_s: Optional[Dict[str, float]] = None, policy: str = "optimal"):
        self.G, self.wards, self.stations = G, list(wards), list(stations)
        self.targets_s = targets_s or get_targets_s()
        self.policy = policy
        self.units: List[Unit] = units_from_stations(self.stations)
        self.baseline = compute_coverage(G, self.wards, providers_from_units(self.units),
                                         self.targets_s, None)
        self.alerts = AlertEngine(self.targets_s)

    def reset(self) -> None:
        self.units = units_from_stations(self.stations)
        self.alerts.reset()

    def update(self, road_state: Optional[RoadState] = None,
               incidents: Sequence[Incident] = (), now: float = 0.0) -> Snapshot:
        res = dispatch(self.G, incidents, self.units, road_state, now, self.policy) if incidents else None
        if res is not None:
            self.units = res.units
        cov = compute_coverage(self.G, self.wards, providers_from_units(self.units, now),
                               self.targets_s, road_state)
        alerts = self.alerts.evaluate(self.baseline, cov, res)
        return Snapshot(cov, coverage_summary(cov), res, alerts)

    def preposition(self, road_state: Optional[RoadState] = None, now: float = 0.0,
                    max_moves: int = 3, candidate_nodes=None) -> PrepositionPlan:
        return recommend_prepositioning(self.G, self.wards, self.units, self.targets_s,
                                        road_state, now, max_moves, candidate_nodes=candidate_nodes)
