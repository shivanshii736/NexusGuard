"""Travel-time routing on the (hazard-modified) road graph.

Graph contract (from P1): networkx (Multi)DiGraph, edge attr `travel_time`
in seconds (peak multipliers already applied). Falls back to length/speed.
Hazards arrive as a RoadState; we never mutate or copy the graph, we just
wrap the weight function (closed edge -> invisible, slow edge -> multiplied).
"""
from __future__ import annotations

import math
from typing import Dict, Iterable, List, Optional, Tuple

import networkx as nx

from .models import Node, RoadState
from .settings import FALLBACK_SPEED_MPS

INF = math.inf


def _edge_cost(attrs: dict, weight: str) -> Optional[float]:
    w = attrs.get(weight)
    if w is None:
        length = attrs.get("length")
        if length is None:
            return None
        w = float(length) / FALLBACK_SPEED_MPS
    return float(w)


def weight_fn(G: nx.Graph, state: Optional[RoadState] = None, weight: str = "travel_time",
              reverse: bool = False):
    """Build a networkx weight callable honouring closures and slowdowns.

    reverse=True is for searching on G.reverse(copy=False): the callable then
    receives (v, u) for original edge (u, v), so we swap back before lookup.
    """
    closed = state.closed if state else frozenset()
    slow = state.slow if state else {}
    multi = G.is_multigraph()

    def fn(a, b, d):
        u, v = (b, a) if reverse else (a, b)
        if (u, v) in closed:
            return None
        attrs_iter = d.values() if multi else (d,)
        best = None
        for attrs in attrs_iter:
            c = _edge_cost(attrs, weight)
            if c is not None and (best is None or c < best):
                best = c
        if best is None:
            return None
        return best * slow.get((u, v), 1.0)

    return fn


def travel_times_from(G, source: Node, state: Optional[RoadState] = None,
                      cutoff: Optional[float] = None, weight: str = "travel_time") -> Dict[Node, float]:
    """Seconds from `source` to every reachable node."""
    if source not in G:
        return {}
    return dict(nx.single_source_dijkstra_path_length(G, source, cutoff=cutoff,
                                                      weight=weight_fn(G, state, weight)))


def travel_times_to(G, target: Node, state: Optional[RoadState] = None,
                    cutoff: Optional[float] = None, weight: str = "travel_time") -> Dict[Node, float]:
    """Seconds from every node TO `target` (one search answers 'who can reach this incident?')."""
    if target not in G:
        return {}
    R = G.reverse(copy=False)
    return dict(nx.single_source_dijkstra_path_length(R, target, cutoff=cutoff,
                                                      weight=weight_fn(G, state, weight, reverse=True)))


def multi_source_times(G, sources: Iterable[Node], state: Optional[RoadState] = None,
                       cutoff: Optional[float] = None, weight: str = "travel_time") -> Dict[Node, float]:
    """Seconds from the NEAREST of `sources` to every node."""
    srcs = [s for s in sources if s in G]
    if not srcs:
        return {}
    return dict(nx.multi_source_dijkstra_path_length(G, srcs, cutoff=cutoff,
                                                     weight=weight_fn(G, state, weight)))


def eta(G, src: Node, dst: Node, state: Optional[RoadState] = None,
        weight: str = "travel_time") -> float:
    """Shortest travel time src -> dst in seconds (inf if unreachable)."""
    if src not in G or dst not in G:
        return INF
    try:
        return float(nx.dijkstra_path_length(G, src, dst, weight=weight_fn(G, state, weight)))
    except nx.NetworkXNoPath:
        return INF


def route(G, src: Node, dst: Node, state: Optional[RoadState] = None,
          weight: str = "travel_time") -> Tuple[float, List[Node]]:
    """(seconds, node path) for the map layer; (inf, []) if unreachable."""
    if src not in G or dst not in G:
        return INF, []
    try:
        t, path = nx.single_source_dijkstra(G, src, dst, weight=weight_fn(G, state, weight))
        return float(t), list(path)
    except nx.NetworkXNoPath:
        return INF, []


def isolated_nodes(G, state: Optional[RoadState], anchor: Node) -> set:
    """Nodes that can no longer reach `anchor` (accessibility view for the UI)."""
    reach = travel_times_to(G, anchor, state)
    return set(G.nodes) - set(reach)
