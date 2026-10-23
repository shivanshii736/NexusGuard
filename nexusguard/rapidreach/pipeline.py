"""One call = one full refresh of the live picture (slide 10 live-mode loop):
update road graph -> recalculate ETAs + available crews -> coverage with free crews only."""
from __future__ import annotations
from dataclasses import dataclass
import networkx as nx

from .hazards import HazardEffect
from .roadstate import road_state
from .toy_graph import Asset, TARGETS_S


@dataclass
class Evaluation:
    effect: HazardEffect
    H0: nx.Graph               # baseline road state (no hazards, same time of day)
    H: nx.Graph                # road state with hazards
    cov0: dict                 # baseline coverage, all crews at base
    cov: dict                  # coverage now: ONLY crews not committed to an incident count
    assignments: list
    committed: set
    free_assets: list[Asset]


def evaluate(G: nx.Graph, assets: list[Asset], effect: HazardEffect, engine, hour: int | None = None,
             targets_s: dict = TARGETS_S) -> Evaluation:
    H0, H = road_state(G, None, hour=hour), road_state(G, effect, hour=hour)
    assignments = engine.dispatch(H, effect.incidents, assets, targets_s)
    committed = {a.asset_id for a in assignments if a.asset_id}
    free = [a for a in assets if a.id not in committed]
    return Evaluation(effect, H0, H, engine.coverage(H0, assets, targets_s),
                      engine.coverage(H, free, targets_s), assignments, committed, free)
