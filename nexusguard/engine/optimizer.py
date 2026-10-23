"""Pre-positioning optimizer  (P2 second deliverable).

recommend_prepositioning() greedily relocates FREE crews to staging nodes that gain the
most population-weighted ward coverage, then reports coverage before vs after.

Speed trick: instead of one search per candidate site we run ONE reverse search per ward
centroid (cutoff = target). Any node found is a site that covers that ward, so every graph
node is a candidate at no extra routing cost; the rest is vectorised numpy.
"""
from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd

from .coverage import compare_coverage, compute_coverage, coverage_summary, providers_from_units
from .models import SERVICES, RoadState, Unit, Ward
from .routing import travel_times_to
from .settings import get_targets_s

INF = math.inf


@dataclass
class Move:
    unit_id: str
    service: str
    from_node: object
    to_node: object
    wards_gained: List[str]
    population_gained: float


@dataclass
class PrepositionPlan:
    moves: List[Move] = field(default_factory=list)
    before: Optional[pd.DataFrame] = None        # ward x service coverage, current positions
    after: Optional[pd.DataFrame] = None         # same, after applying the moves
    summary_before: Optional[pd.DataFrame] = None
    summary_after: Optional[pd.DataFrame] = None

    def moves_frame(self) -> pd.DataFrame:
        return pd.DataFrame([{**dataclasses.asdict(m), "wards_gained": ", ".join(m.wards_gained)}
                             for m in self.moves])

    def comparison(self) -> pd.DataFrame:
        return compare_coverage(self.before, self.after)


def _reach_matrix(G, wards, target, state, candidate_nodes):
    """T[c, w] = seconds from candidate c to ward w centroid (inf if beyond target)."""
    reach = [travel_times_to(G, w.centroid, state, cutoff=target) for w in wards]
    if candidate_nodes is None:
        cands = sorted({n for r in reach for n in r}, key=str)
    else:
        cands = [n for n in candidate_nodes if n in G]
    idx = {n: i for i, n in enumerate(cands)}
    T = np.full((len(cands), len(wards)), INF)
    for j, r in enumerate(reach):
        for n, t in r.items():
            i = idx.get(n)
            if i is not None:
                T[i, j] = t
    return cands, T, reach


def _unit_matrix(units, reach):
    return np.array([[r.get(u.home_node, INF) for r in reach] for u in units], dtype=float).reshape(len(units), len(reach))


def recommend_prepositioning(G, wards: Sequence[Ward], units: Sequence[Unit],
                             targets_s: Optional[Dict[str, float]] = None,
                             road_state: Optional[RoadState] = None, now: float = 0.0,
                             max_moves: int = 3, services: Sequence[str] = SERVICES,
                             candidate_nodes: Optional[Iterable] = None) -> PrepositionPlan:
    """Up to `max_moves` relocations per service, each chosen for the biggest coverage gain."""
    targets_s = targets_s or get_targets_s()
    pop = np.array([w.population for w in wards], dtype=float)
    cand_list = list(candidate_nodes) if candidate_nodes is not None else None

    moves: List[Move] = []
    for svc in services:
        target = targets_s[svc]
        free = [u for u in units if u.kind == svc and u.is_free(now)]
        if not free or not wards:
            continue
        cands, T, reach = _reach_matrix(G, wards, target, road_state, cand_list)
        if not cands:
            continue
        cur = _unit_matrix(free, reach)               # (U, W)
        moved: set = set()
        for _ in range(max_moves):
            cur_best = cur.min(axis=0)
            cur_cov = float((pop * (cur_best <= target)).sum())
            best = None                               # (cov, -eta_sum, unit_i, cand_i)
            for i in range(len(free)):
                if i in moved:
                    continue
                others = np.delete(cur, i, axis=0)
                base = others.min(axis=0) if others.shape[0] else np.full(len(wards), INF)
                new = np.minimum(base[None, :], T)            # (C, W)
                covered = new <= target
                cov = (covered * pop).sum(axis=1)
                eta_sum = (np.where(covered, new, 0.0) * pop).sum(axis=1)
                order = np.lexsort((eta_sum, -cov))           # max cov, then min eta
                c = int(order[0])
                key = (float(cov[c]), -float(eta_sum[c]))
                if best is None or key > best[0]:
                    best = (key, i, c)
            if best is None or best[0][0] <= cur_cov + 1e-9:
                break
            _, i, c = best
            old_cov_mask = cur_best <= target
            others = np.delete(cur, i, axis=0)
            base = others.min(axis=0) if others.shape[0] else np.full(len(wards), INF)
            new_mask = np.minimum(base, T[c]) <= target
            gain_mask = new_mask & ~old_cov_mask
            moves.append(Move(free[i].id, svc, free[i].home_node, cands[c],
                              [wards[j].name for j in np.where(gain_mask)[0]],
                              float(pop[gain_mask].sum())))
            cur[i] = T[c]
            moved.add(i)

    plan = PrepositionPlan(moves=moves)
    plan.before = compute_coverage(G, wards, providers_from_units(units, now), targets_s, road_state)
    plan.after = compute_coverage(G, wards, providers_from_units(apply_plan(units, plan), now), targets_s, road_state)
    plan.summary_before = coverage_summary(plan.before)
    plan.summary_after = coverage_summary(plan.after)
    return plan


def apply_plan(units: Sequence[Unit], plan: PrepositionPlan) -> List[Unit]:
    """Return units with the recommended moves applied (home_node becomes the staging node)."""
    dest = {m.unit_id: m.to_node for m in plan.moves}
    return [dataclasses.replace(u, home_node=dest[u.id]) if u.id in dest else u for u in units]


def rank_staging_sites(G, wards: Sequence[Ward], units: Sequence[Unit], service: str,
                       targets_s: Optional[Dict[str, float]] = None,
                       road_state: Optional[RoadState] = None, now: float = 0.0,
                       top_n: int = 10, candidate_nodes: Optional[Iterable] = None) -> pd.DataFrame:
    """Rank sites by population coverage gained if ONE extra crew were staged there."""
    targets_s = targets_s or get_targets_s()
    target = targets_s[service]
    pop = np.array([w.population for w in wards], dtype=float)
    cands, T, reach = _reach_matrix(G, wards, target, road_state,
                                    list(candidate_nodes) if candidate_nodes is not None else None)
    free = [u for u in units if u.kind == service and u.is_free(now)]
    cur = _unit_matrix(free, reach).min(axis=0) if free else np.full(len(wards), INF)
    newly = (T <= target) & (cur[None, :] > target)
    gain = (newly * pop).sum(axis=1)
    order = np.argsort(-gain, kind="stable")[:top_n]
    return pd.DataFrame([{"node": cands[i], "service": service, "wards_gained": int(newly[i].sum()),
                          "population_gained": float(gain[i]),
                          "ward_names": ", ".join(wards[j].name for j in np.where(newly[i])[0])}
                         for i in order if gain[i] > 0])
