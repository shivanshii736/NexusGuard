from nexusguard.engine.coverage import compute_coverage, providers_from_stations
from nexusguard.engine.models import RoadState
from nexusguard.network.adapters import to_stations, to_wards
from tests.toy_graph import make_toy


def test_cutting_off_a_station_degrades_coverage():
    G, assets, zones = make_toy()
    wards, providers = to_wards(zones), providers_from_stations(to_stations(assets))
    base = compute_coverage(G, wards, providers, services=("fire",))
    # cut off fire station A (node 8) by closing every road touching it
    closed = frozenset((u, v) for u, v in G.edges() if 8 in (u, v))
    hit = compute_coverage(G, wards, providers, state=RoadState(closed=closed), services=("fire",))
    assert hit["covered"].mean() < base["covered"].mean()
    print(f"fire coverage {base['covered'].mean():.0%} -> {hit['covered'].mean():.0%}")
