"""PERSON 1. Build the drive graph for the study area, add peak_time, cache to disk.

Pipeline (see build_graph()):
  OSM drive graph for bbox -> free-flow speeds -> travel_time (s) -> peak_time (s, ASSUMED multipliers)
  -> keep largest STRONGLY connected component -> save graphml.

Contract (types.py): MultiDiGraph, edges have length (m), travel_time (s), peak_time (s); nodes have x, y.
CLI:  python -m nexusguard.network.build_graph            # build + cache + validate
      python -m nexusguard.network.build_graph --check    # validate the existing cache only
"""
from __future__ import annotations

import ast
import time
from pathlib import Path

import networkx as nx

from nexusguard import config


# ---------------------------------------------------------------- pure functions (no osmnx, no network)
def _hw_class(hw) -> str:
    """OSM 'highway' can be a str, a list (merged ways) or a stringified list (after graphml reload)."""
    if isinstance(hw, str) and hw.startswith("["):
        try:
            hw = ast.literal_eval(hw)
        except (ValueError, SyntaxError):
            pass
    if isinstance(hw, (list, tuple)):
        hw = hw[0] if hw else "default"
    hw = str(hw) if hw else "default"
    return hw[:-5] if hw.endswith("_link") else hw      # primary_link -> primary


def add_peak_time(G: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """Set edge['peak_time'] = edge['travel_time'] * multiplier(highway class). Multipliers are ASSUMED."""
    for _, _, d in G.edges(data=True):
        mult = config.PEAK_MULTIPLIERS.get(_hw_class(d.get("highway", "default")),
                                           config.PEAK_MULTIPLIERS["default"])
        d["peak_time"] = d["travel_time"] * mult
    return G


def largest_scc(G: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """Keep only the largest strongly connected component, so every node can reach every other
    (no dead-end islands that would give inf ETAs for no real reason)."""
    nodes = max(nx.strongly_connected_components(G), key=len)
    return G.subgraph(nodes).copy()


def validate_graph(G: nx.MultiDiGraph) -> dict:
    """Assert the shared contract holds; return a small stats dict. Raises AssertionError on violation."""
    assert isinstance(G, nx.MultiDiGraph), "must be a MultiDiGraph"
    assert G.number_of_nodes() > 0 and G.number_of_edges() > 0, "empty graph"
    assert all("x" in d and "y" in d for _, d in G.nodes(data=True)), "node missing x/y"
    for u, v, k, d in G.edges(keys=True, data=True):
        for a in ("length", "travel_time", "peak_time"):
            assert isinstance(d.get(a), (int, float)), f"edge {(u, v, k)} missing/non-numeric {a}: {d.get(a)!r}"
        assert d["travel_time"] > 0 and d["peak_time"] >= d["travel_time"], f"bad times on {(u, v, k)}"
    assert nx.is_strongly_connected(G), "graph is not strongly connected"
    ratio = sum(d["peak_time"] for *_, d in G.edges(data=True)) / sum(d["travel_time"] for *_, d in G.edges(data=True))
    return {"nodes": G.number_of_nodes(), "edges": G.number_of_edges(), "avg_peak_slowdown": round(ratio, 2)}


# ---------------------------------------------------------------- osmnx-dependent
def _download(bbox):
    import osmnx as ox
    Path("data/raw/osm_cache").mkdir(parents=True, exist_ok=True)
    ox.settings.use_cache = True                     # re-runs reuse the Overpass response
    ox.settings.cache_folder = "data/raw/osm_cache"
    ox.settings.log_console = True
    if bbox is None:
        return ox.graph_from_place(config.STUDY_AREA_NAME, network_type="drive")
    n, s, e, w = bbox
    if int(ox.__version__.split(".")[0]) >= 2:       # osmnx 2.x: bbox=(left, bottom, right, top)
        return ox.graph_from_bbox((w, s, e, n), network_type="drive")
    return ox.graph_from_bbox(north=n, south=s, east=e, west=w, network_type="drive")  # osmnx 1.x


def build_graph(bbox=config.STUDY_AREA_BBOX, cache_path: str = config.GRAPH_CACHE) -> nx.MultiDiGraph:
    import osmnx as ox
    t0 = time.time()
    G = _download(bbox)
    print(f"[1/5] downloaded: {len(G):,} nodes, {G.number_of_edges():,} edges ({time.time()-t0:.0f}s)")

    G = ox.add_edge_speeds(G, hwy_speeds=config.FREEFLOW_SPEEDS_KMH, fallback=config.FREEFLOW_FALLBACK_KMH)
    G = ox.add_edge_travel_times(G)                  # travel_time = length / speed, seconds
    print("[2/5] speeds + travel_time added")

    G = add_peak_time(G)
    print("[3/5] peak_time added (ASSUMED multipliers)")

    before = len(G)
    G = largest_scc(G)
    print(f"[4/5] largest strongly connected component: kept {len(G):,} of {before:,} nodes")

    stats = validate_graph(G)
    Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
    ox.save_graphml(G, cache_path)
    print(f"[5/5] cached to {cache_path} ({Path(cache_path).stat().st_size/1e6:.1f} MB). {stats}")
    return G


def load_graph(use_cache: bool = True) -> nx.MultiDiGraph:
    """Load from cache if present (demo must work OFFLINE); otherwise build, then cache."""
    path = Path(config.GRAPH_CACHE)
    if use_cache and path.exists():
        import osmnx as ox
        G = ox.load_graphml(path)
        # graphml stores everything as text; osmnx restores only its own attrs, so coerce ours.
        for _, _, d in G.edges(data=True):
            for a in ("length", "travel_time", "peak_time"):
                d[a] = float(d[a])
        validate_graph(G)                            # fail loudly if the cache is stale/corrupt
        return G
    return build_graph()


if __name__ == "__main__":
    import sys
    if "--check" in sys.argv:
        print(validate_graph(load_graph(use_cache=True)))
    else:
        build_graph()
