"""Apply a merged HazardEffect to a base graph -> graph with `travel_time_s` per edge.

This is the "road-state model" box in the deck: close inaccessible edges, apply slowdown
travel costs (and optional time-of-day multipliers). The base graph is never mutated.
"""
from __future__ import annotations
import networkx as nx

from .hazards import HazardEffect
from .toy_graph import edge_key
from .traffic import DEFAULT_PEAK_HOUR, time_multiplier


def road_state(G: nx.Graph, effect: HazardEffect | None = None, peak: bool = False,
               hour: int | None = None) -> nx.Graph:
    """`hour` (0-23) applies the assumed time-of-day multipliers; `peak=True` is shorthand for hour 18."""
    if hour is None and peak:
        hour = DEFAULT_PEAK_HOUR
    H = G.copy()
    effect = effect or HazardEffect()
    for u, v, d in H.edges(data=True):
        t = d["base_time_s"]
        if hour is not None:
            t *= time_multiplier(hour, d["road_class"])
        t *= effect.slowdowns.get(edge_key(u, v), 1.0)
        d["travel_time_s"] = t
    H.remove_edges_from([tuple(e) for e in effect.closed_edges if H.has_edge(*e)])
    H.graph["closed_edges"] = set(effect.closed_edges)   # lets engines stage crews at a cordon
    return H
