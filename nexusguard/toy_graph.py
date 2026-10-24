"""Toy road network used until the OSMnx graph (P1) is plugged in.

A 7x7 grid (~600 m spacing) near central Bengaluru with:
  * node attrs: lat, lon, elevation (m, a low-lying basin in the middle), ward
  * edge attrs: length_m, base_speed_kph, road_class, underpass(bool), base_time_s
  * 9 wards, hospital (ambulance) bases, fire stations, one rescue unit.

Edge identity everywhere in this package is a sorted node pair `(u, v)`; see `edge_key`.
"""
from __future__ import annotations
from dataclasses import dataclass
import networkx as nx

from .geo import haversine_m

N = 7
ORIGIN = (12.9500, 77.5700)          # south-west corner
D_LAT, D_LON = 0.0054, 0.0055        # ~600 m per step


def edge_key(u: int, v: int) -> tuple[int, int]:
    return (u, v) if u <= v else (v, u)


def node_id(r: int, c: int) -> int:
    return r * N + c


@dataclass(frozen=True)
class Asset:
    id: str
    service: str            # "ambulance" | "fire" | "rescue"
    node: int


def _elevation(r: int, c: int) -> float:
    """Gentle slope (north is higher) plus a basin around (r=2..3, c=2..4)."""
    base = 0.25 * r
    basin = -1.6 * max(0.0, 1 - ((r - 2.5) ** 2 + (c - 3) ** 2) / 5.0)
    return round(max(0.0, base + 1.2 + basin), 2)


def build_toy_graph() -> nx.Graph:
    G = nx.Graph(name="toy-bengaluru")
    for r in range(N):
        for c in range(N):
            G.add_node(
                node_id(r, c),
                lat=ORIGIN[0] + r * D_LAT,
                lon=ORIGIN[1] + c * D_LON,
                elevation=_elevation(r, c),
                ward=f"W{(r * 3 // N) * 3 + (c * 3 // N) + 1}",
                label=f"({r},{c})",
            )

    def add(u: int, v: int, road_class: str, speed: float):
        a, b = G.nodes[u], G.nodes[v]
        length = haversine_m(a["lat"], a["lon"], b["lat"], b["lon"])
        G.add_edge(
            *edge_key(u, v),
            length_m=length,
            base_speed_kph=speed,
            road_class=road_class,
            underpass=False,
            base_time_s=length / (speed / 3.6),
        )

    for r in range(N):
        for c in range(N):
            u = node_id(r, c)
            # arterial roads every third row/column, local roads elsewhere
            if c + 1 < N:
                arterial = r % 3 == 0
                add(u, node_id(r, c + 1), "arterial" if arterial else "local", 30 if arterial else 18)
            if r + 1 < N:
                arterial = c % 3 == 0
                add(u, node_id(r + 1, c), "arterial" if arterial else "local", 30 if arterial else 18)

    # a railway underpass in the basin: floods first, the classic failure point
    G.edges[edge_key(node_id(2, 3), node_id(3, 3))]["underpass"] = True
    return G


def default_assets() -> list[Asset]:
    return [
        Asset("AMB-1", "ambulance", node_id(1, 1)),   # hospital proxies
        Asset("AMB-2", "ambulance", node_id(5, 5)),
        Asset("AMB-3", "ambulance", node_id(3, 6)),
        Asset("FIRE-1", "fire", node_id(0, 3)),
        Asset("FIRE-2", "fire", node_id(6, 1)),
        Asset("RESC-1", "rescue", node_id(6, 6)),
    ]


# response-time targets per service, seconds (assumptions - the deck's "configured targets")
TARGETS_S = {"ambulance": 480, "fire": 600, "rescue": 900}
