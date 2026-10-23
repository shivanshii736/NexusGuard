"""Self-contained 7x7 grid so engine tests don't depend on tests/toy_graph.py."""
import networkx as nx
from nexusguard.engine.models import Station, Ward

STEP = 60.0  # seconds per block


def grid(n=7):
    G = nx.MultiDiGraph()
    for r in range(n):
        for c in range(n):
            for dr, dc in ((0, 1), (1, 0)):
                rr, cc = r + dr, c + dc
                if rr < n and cc < n:
                    G.add_edge((r, c), (rr, cc), travel_time=STEP)
                    G.add_edge((rr, cc), (r, c), travel_time=STEP)
    return G


def wards():
    return [Ward(id=f"w{r}{c}", name=f"Ward {r}{c}", centroid=(r, c)) for r in (1, 3, 5) for c in (1, 3, 5)]


def stations():
    return [Station("A1", "Amb NW", "ambulance", (0, 0)), Station("A2", "Amb SE", "ambulance", (6, 6)),
            Station("F1", "Fire C", "fire", (3, 3)), Station("R1", "Rescue C", "rescue", (3, 3))]


TARGETS = {"ambulance": 300.0, "fire": 240.0, "rescue": 480.0}   # 5 / 4 / 8 min = 5 / 4 / 8 blocks
