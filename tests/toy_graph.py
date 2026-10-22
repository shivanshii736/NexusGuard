"""A tiny synthetic city so nobody waits for OSM. 7x7 grid, ~400 m spacing near central Bengaluru."""
import networkx as nx
from nexusguard.types import Asset, Zone


def make_toy(n: int = 7):
    G = nx.MultiDiGraph()
    lat0, lon0, step = 12.97, 77.59, 0.0036   # ~400 m
    nid = lambda r, c: r * n + c
    for r in range(n):
        for c in range(n):
            G.add_node(nid(r, c), y=lat0 + r * step, x=lon0 + c * step)
    for r in range(n):
        for c in range(n):
            for dr, dc in ((0, 1), (1, 0)):
                rr, cc = r + dr, c + dc
                if rr < n and cc < n:
                    for u, v in ((nid(r, c), nid(rr, cc)), (nid(rr, cc), nid(r, c))):
                        # 400 m at 30 km/h = 48 s free-flow; peak x2
                        G.add_edge(u, v, 0, length=400.0, travel_time=48.0, peak_time=96.0, highway="secondary")
    assets = [Asset("fire-A", "fire", nid(1, 1), "Fire A"), Asset("fire-B", "fire", nid(5, 5), "Fire B"),
              Asset("amb-A", "ambulance", nid(1, 5), "Hospital A", is_proxy=True),
              Asset("amb-B", "ambulance", nid(5, 1), "Hospital B", is_proxy=True)]
    zones = [Zone(f"z{r}{c}", f"Ward {r}{c}", nid(r, c), population=1000)
             for r in range(0, n, 2) for c in range(0, n, 2)]
    return G, assets, zones
