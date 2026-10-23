"""Ward-level response coverage per service (ambulance / fire / rescue)."""
from __future__ import annotations

import math
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

from .models import SERVICES, RoadState, Station, Unit, Ward
from .routing import multi_source_times
from .settings import get_targets_s

Provider = Tuple[str, object]   # (service kind, graph node)


def providers_from_stations(stations: Iterable[Station]) -> List[Provider]:
    return [(s.kind, s.node) for s in stations]


def providers_from_units(units: Iterable[Unit], now: float = 0.0) -> List[Provider]:
    """Only FREE crews count: committed crews degrade live coverage."""
    return [(u.kind, u.home_node) for u in units if u.is_free(now)]


def compute_coverage(G, wards: Sequence[Ward], providers: Iterable[Provider],
                     targets_s: Optional[Dict[str, float]] = None,
                     state: Optional[RoadState] = None,
                     services: Sequence[str] = SERVICES) -> pd.DataFrame:
    """One row per (ward, service).

    eta_s          travel time from the nearest provider to the ward centroid (inf = unreachable)
    covered        eta_s <= target
    pct_nodes_covered  share of the ward's nodes within target (centroid only if ward.nodes empty)
    gap_s          seconds over target (0 if covered)
    """
    targets_s = targets_s or get_targets_s()
    providers = list(providers)
    rows = []
    for svc in services:
        target = targets_s[svc]
        sources = [n for k, n in providers if k == svc]
        times = multi_source_times(G, sources, state)          # full search; nodes beyond reach absent
        for w in wards:
            eta = times.get(w.centroid, math.inf)
            nodes = w.nodes or (w.centroid,)
            pct = sum(1 for n in nodes if times.get(n, math.inf) <= target) / len(nodes)
            rows.append({
                "ward_id": w.id, "ward": w.name, "service": svc,
                "eta_s": eta, "target_s": target, "covered": eta <= target,
                "pct_nodes_covered": pct, "population": w.population,
                "gap_s": 0.0 if eta <= target else eta - target,
            })
    return pd.DataFrame(rows)


def coverage_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Per-service headline numbers for the dashboard."""
    out = []
    for svc, g in df.groupby("service", sort=False):
        pop = g["population"].sum()
        finite = g["eta_s"][g["eta_s"] < math.inf]
        out.append({
            "service": svc,
            "wards_total": len(g),
            "wards_covered": int(g["covered"].sum()),
            "pct_wards_covered": 100.0 * g["covered"].mean(),
            "pct_population_covered": 100.0 * g.loc[g["covered"], "population"].sum() / pop if pop else 0.0,
            "unreachable_wards": int((g["eta_s"] == math.inf).sum()),
            "median_eta_s": float(finite.median()) if len(finite) else math.inf,
            "worst_eta_s": float(g["eta_s"].max()),
        })
    return pd.DataFrame(out)


def compare_coverage(before: pd.DataFrame, after: pd.DataFrame) -> pd.DataFrame:
    """Before/after join: powers the 'coverage before vs after pre-positioning' view."""
    m = before.merge(after, on=["ward_id", "ward", "service"], suffixes=("_before", "_after"))
    m["eta_change_s"] = m["eta_s_after"] - m["eta_s_before"]
    m["newly_covered"] = (~m["covered_before"]) & m["covered_after"]
    m["newly_uncovered"] = m["covered_before"] & (~m["covered_after"])
    keep = ["ward_id", "ward", "service", "eta_s_before", "eta_s_after", "eta_change_s",
            "covered_before", "covered_after", "newly_covered", "newly_uncovered"]
    return m[keep]
