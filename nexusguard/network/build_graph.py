"""PERSON 1. Build the Bengaluru drive graph, add peak_time, cache to disk."""
import networkx as nx
from nexusguard import config


def add_peak_time(G: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """Set edge['peak_time'] = edge['travel_time'] * multiplier(highway class)."""
    for _, _, d in G.edges(data=True):
        hw = d.get("highway", "default")
        hw = hw[0] if isinstance(hw, list) else hw
        mult = config.PEAK_MULTIPLIERS.get(hw, config.PEAK_MULTIPLIERS["default"])
        d["peak_time"] = d["travel_time"] * mult
    return G


def load_graph(use_cache: bool = True) -> nx.MultiDiGraph:
    """TODO(P1): osmnx.graph_from_place / graph_from_bbox -> add_edge_speeds ->
    add_edge_travel_times -> add_peak_time -> save_graphml(GRAPH_CACHE).
    Demo must work OFFLINE: always load from cache when it exists."""
    raise NotImplementedError
