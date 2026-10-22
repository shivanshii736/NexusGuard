"""PERSON 2. RoadState + graph -> effective graph and ETAs. Working reference implementation."""
import networkx as nx
from nexusguard.types import RoadState


def effective_graph(G: nx.MultiDiGraph, state: RoadState, peak: bool = True) -> nx.MultiDiGraph:
    """Copy of G with closed edges removed and slowdowns applied to edge['eta'] (seconds)."""
    H = G.copy()
    base = "peak_time" if peak else "travel_time"
    H.remove_edges_from([e for e in state.closed_edges if H.has_edge(*e)])
    for u, v, k, d in H.edges(keys=True, data=True):
        d["eta"] = d[base] * state.slowdown.get((u, v, k), 1.0)
    return H


def nearest_asset_eta(H: nx.MultiDiGraph, source_nodes: list[int]) -> dict:
    """Seconds from the NEAREST source node to every reachable node.
    One multi-source Dijkstra on the reversed graph = response time TO each node."""
    if not source_nodes:
        return {}
    return nx.multi_source_dijkstra_path_length(H.reverse(copy=False), source_nodes, weight="eta")
