"""Pre-positioning recommendations (stand-in: P2 may own the real optimiser).

Two questions from the deck:
  * Planning: "Rank candidate staging sites by coverage improvement"  -> rank_staging_sites()
  * Live:     "Reassign available crews; test staging"                -> recommend_moves()

Coverage = nodes reachable from any unit within that service's response-time target.
Candidate sites are all nodes still connected to a road; scoring is (city-wide coverage,
worst ward) lexicographic, ties broken by node id so results are deterministic.
"""
from __future__ import annotations
from dataclasses import dataclass
import networkx as nx

from .toy_graph import Asset, TARGETS_S


@dataclass
class Move:
    service: str
    asset_id: str
    from_node: int
    to_node: int
    city_before: float
    city_after: float
    worst_before: float
    worst_after: float


@dataclass
class Site:
    service: str
    node: int
    city_before: float
    city_after: float
    newly_covered: int


def _reach_sets(H: nx.Graph, target_s: float) -> dict[int, set[int]]:
    return {n: set(nx.single_source_dijkstra_path_length(H, n, weight="travel_time_s", cutoff=target_s))
            for n in H.nodes}


def _ward_nodes(H: nx.Graph) -> dict[str, set[int]]:
    w: dict[str, set[int]] = {}
    for n, d in H.nodes(data=True):
        w.setdefault(d["ward"], set()).add(n)
    return w


def _score(H: nx.Graph, covered: set[int], wards: dict[str, set[int]]) -> tuple[float, float]:
    city = len(covered) / H.number_of_nodes()
    worst = min(len(covered & ns) / len(ns) for ns in wards.values())
    return city, worst


def _candidates(H: nx.Graph) -> list[int]:
    return sorted(n for n in H.nodes if H.degree(n) > 0)


def recommend_moves(H: nx.Graph, free_assets: list[Asset], targets_s: dict = TARGETS_S) -> list[Move]:
    """Best single relocation of an AVAILABLE unit, per service, only if it improves coverage."""
    wards, cands = _ward_nodes(H), _candidates(H)
    moves: list[Move] = []
    for svc, target in targets_s.items():
        units = [a for a in free_assets if a.service == svc]
        if not units:
            continue
        reach = _reach_sets(H, target)
        base_cov = set().union(*(reach[a.node] for a in units))
        base = _score(H, base_cov, wards)
        best = None
        for u in units:
            rest = set().union(*(reach[o.node] for o in units if o.id != u.id)) if len(units) > 1 else set()
            for n in cands:
                if n == u.node:
                    continue
                sc = _score(H, rest | reach[n], wards)
                key = (sc, -n, u.id)
                if best is None or key > best[0]:
                    best = (key, u, n, sc)
        if best and best[3] > base:
            _, u, n, sc = best
            moves.append(Move(svc, u.id, u.node, n, base[0], sc[0], base[1], sc[1]))
    return moves


def rank_staging_sites(H: nx.Graph, assets: list[Asset], service: str, targets_s: dict = TARGETS_S,
                       top_k: int = 5) -> list[Site]:
    """Where would ONE extra staged vehicle of `service` add the most coverage?"""
    reach = _reach_sets(H, targets_s[service])
    have = set().union(*(reach[a.node] for a in assets if a.service == service)) if any(
        a.service == service for a in assets) else set()
    before = len(have) / H.number_of_nodes()
    sites = [Site(service, n, before, len(have | reach[n]) / H.number_of_nodes(), len(reach[n] - have))
             for n in _candidates(H)]
    sites = [s for s in sites if s.newly_covered > 0]
    return sorted(sites, key=lambda s: (-s.newly_covered, s.node))[:top_k]


def apply_moves(assets: list[Asset], moves: list[Move]) -> list[Asset]:
    to = {m.asset_id: m.to_node for m in moves}
    return [Asset(a.id, a.service, to.get(a.id, a.node)) for a in assets]
