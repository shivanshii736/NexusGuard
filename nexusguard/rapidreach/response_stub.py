"""STAND-IN for the shared response engine (P1/P2 own the real one).

It exists so the P3 app runs end to end today. Swap it by passing any object with the same
two methods:

    engine.coverage(road_graph, assets, targets_s) -> {ward: {service: fraction_covered}}
    engine.dispatch(road_graph, incidents, assets, targets_s) -> list[Assignment]

Dispatch is deterministic and greedy: incidents by severity (then id), each required unit goes
to the nearest still-free unit of that service (resource contention: a unit serves one call).
Assignment.path is the travel-time-shortest route, used by the UI to draw affected routes.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import networkx as nx

from .toy_graph import Asset, TARGETS_S

STAGING_PENALTY_S = 90   # ASSUMPTION: extra time to reach a cordoned incident from the cordon edge


@dataclass
class Assignment:
    incident_id: str
    service: str
    asset_id: str | None      # None = no free / reachable unit
    eta_s: float | None
    target_s: float
    breach: bool
    path: list[int] = field(default_factory=list)   # node ids, asset base -> incident (or cordon edge)
    staged: bool = False                            # True if the crew stops at the cordon, not the incident


def _times_from(H: nx.Graph, node: int) -> dict[int, float]:
    return nx.single_source_dijkstra_path_length(H, node, weight="travel_time_s")


def _targets_for(H: nx.Graph, node: int) -> list[tuple[int, float]]:
    """Nodes a crew can aim for: the incident itself, or the cordon boundary if it is cut off."""
    cands = [(node, 0.0)]
    for u, v in sorted(H.graph.get("closed_edges", ())):
        if node in (u, v):
            cands.append((v if u == node else u, STAGING_PENALTY_S))
    return cands


class StubResponseEngine:
    def coverage(self, H: nx.Graph, assets: list[Asset], targets_s: dict = TARGETS_S) -> dict:
        wards: dict[str, list[int]] = {}
        for n, d in H.nodes(data=True):
            wards.setdefault(d["ward"], []).append(n)
        best: dict[str, dict[int, float]] = {}
        for svc in targets_s:
            dist: dict[int, float] = {}
            for a in (x for x in assets if x.service == svc):
                for n, t in _times_from(H, a.node).items():
                    dist[n] = min(dist.get(n, float("inf")), t)
            best[svc] = dist
        return {
            w: {svc: sum(best[svc].get(n, float("inf")) <= targets_s[svc] for n in nodes) / len(nodes)
                for svc in targets_s}
            for w, nodes in sorted(wards.items())
        }

    def dispatch(self, H: nx.Graph, incidents, assets: list[Asset], targets_s: dict = TARGETS_S) -> list[Assignment]:
        committed: set[str] = set()
        cache: dict[str, tuple[dict, dict]] = {}
        out: list[Assignment] = []

        def reach(a: Asset):
            if a.id not in cache:
                cache[a.id] = nx.single_source_dijkstra(H, a.node, weight="travel_time_s")
            return cache[a.id]

        for inc in sorted(incidents, key=lambda i: (-i.severity, i.id)):
            for svc, count in inc.required_units.items():
                target = targets_s.get(svc, 600)
                for _ in range(count):
                    best, best_t, best_path, best_staged = None, float("inf"), [], False
                    for a in (x for x in assets if x.service == svc and x.id not in committed):
                        dist, paths = reach(a)
                        for n, pen in _targets_for(H, inc.node):
                            if n in dist and dist[n] + pen < best_t:
                                best, best_t, best_path, best_staged = a, dist[n] + pen, paths[n], pen > 0
                    if best is None:
                        out.append(Assignment(inc.id, svc, None, None, target, True))
                    else:
                        committed.add(best.id)
                        out.append(Assignment(inc.id, svc, best.id, best_t, target, best_t > target,
                                              list(best_path), best_staged))
        return out
