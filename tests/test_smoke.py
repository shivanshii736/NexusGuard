from tests.toy_graph import make_toy
from nexusguard.types import RoadState
from nexusguard.engine.coverage import coverage


def test_cutting_off_a_station_degrades_coverage():
    G, assets, zones = make_toy()
    base = coverage(G, assets, zones, RoadState(), "fire")
    # cut off fire station A (node 8) by closing every road touching it
    closed = {(u, v, k) for u, v, k in G.edges(keys=True) if 8 in (u, v)}
    hit = coverage(G, assets, zones, RoadState(closed_edges=closed), "fire")
    assert hit.pct_zones < base.pct_zones
    print(f"fire coverage {base.pct_zones:.0%} -> {hit.pct_zones:.0%}")
