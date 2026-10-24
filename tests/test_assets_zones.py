"""P1 tests: assets, zones, baseline. No downloads, no osmnx/geopandas needed."""
import json, os, tempfile
from nexusguard.network.snap import nearest_nodes
from nexusguard.network.assets import _dedupe, _read_fire_csv, load_assets, _is_real_hospital
from nexusguard.network.zones import grid_zones, load_zones, _grid_cells
from nexusguard.network.adapters import to_stations, to_wards
from nexusguard.network.baseline import baseline_report
from nexusguard.types import Asset
from tests.toy_graph import make_toy


def test_snap_finds_exact_node():
    G, _, _ = make_toy()
    n, d = nearest_nodes(G, [G.nodes[8]["x"]], [G.nodes[8]["y"]])
    assert n == [8] and d[0] < 1


def test_dedupe_prefers_first_and_keeps_far_points():
    a = {"kind": "fire", "lon": 77.59, "lat": 12.97, "id": "csv-1"}
    b = {"kind": "fire", "lon": 77.5901, "lat": 12.9701, "id": "osm-1"}   # ~15 m away
    c = {"kind": "fire", "lon": 77.60, "lat": 12.98, "id": "osm-2"}
    h = {"kind": "ambulance", "lon": 77.59, "lat": 12.97, "id": "osm-3"}  # other kind: kept
    assert [r["id"] for r in _dedupe([a, b, c, h])] == ["csv-1", "osm-2", "osm-3"]


def test_fire_csv_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "f.csv")
        open(p, "w").write("id,name,lat,lon,crews\n1,Stn,12.97,77.59,3\n")
        r = _read_fire_csv(p)
        assert r[0]["crews"] == 3 and r[0]["id"] == "csv-1"
    assert _read_fire_csv("does/not/exist.csv") == []


def test_grid_zones_cover_toy_graph_with_valid_nodes():
    G, _, _ = make_toy()
    zones = grid_zones(G, cell_m=1000)
    assert 4 <= len(zones) <= 12
    assert all(z.node in G for z in zones) and len({z.id for z in zones}) == len(zones)


def test_cache_roundtrip_and_stale_cache_rebuilds():
    G, assets, _ = make_toy()
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "assets.json")
        json.dump([a.__dict__ for a in assets], open(p, "w"))
        assert [a.id for a in load_assets(G, cache_path=p)] == [a.id for a in assets]
        zp = os.path.join(d, "zones.json")
        z1 = load_zones(G, cache_path=zp)
        assert [z.id for z in load_zones(G, cache_path=zp)] == [z.id for z in z1]


def test_grid_members_include_each_zone_centroid():
    G, _, _ = make_toy()
    for z, nodes in _grid_cells(G, 1000):
        assert z.node in nodes and len(nodes) >= 3


def test_adapters_map_to_engine_models():
    G, assets, zones = make_toy()
    st = to_stations(assets)
    assert [(s.id, s.kind, s.node, s.units) for s in st] == [(a.id, a.kind, a.node, a.crews) for a in assets]
    from nexusguard.types import Zone
    wards = to_wards([zones[0], Zone("zx", "No pop", zones[1].node)], {zones[0].id: (zones[0].node,)})
    assert wards[0].nodes == (zones[0].node,) and wards[0].population == 1000
    assert wards[1].nodes == () and wards[1].population == 1.0


def test_baseline_report_shape_and_peak_not_better():
    G, assets, zones = make_toy()
    rep = baseline_report(G, assets, zones)
    for svc in ("fire", "ambulance"):
        f, p = rep[svc]["free_flow"], rep[svc]["peak"]
        assert p["covered"] + p["missed"] == p["zones"] == len(zones)
        assert p["covered"] <= f["covered"]


def test_peak_view_swaps_times_without_touching_original():
    from nexusguard.network.adapters import peak_view
    G, _, _ = make_toy()
    H = peak_view(G)
    u, v, k = next(iter(G.edges(keys=True)))
    assert H[u][v][k]["travel_time"] == G[u][v][k]["peak_time"]
    assert G[u][v][k]["travel_time"] == make_toy()[0][u][v][k]["travel_time"]


def test_hospital_filter_drops_clinics():
    assert _is_real_hospital("Manipal Hospital", None)
    assert _is_real_hospital(None, "yes")
    assert not _is_real_hospital("Sri Sai Clinic", None)
    assert not _is_real_hospital(float("nan"), None)

def test_hospital_filter_drops_specialty_clinics():
    assert not _is_real_hospital("Pranam Dental Hospital", None)
    assert not _is_real_hospital("Nethra Eye Hospital", None)
    assert not _is_real_hospital("Dr. T.V.Ramesh Piles Hospital", None)
    assert _is_real_hospital("Orient Hospital", None)
    assert _is_real_hospital("Manipal Hospital", None)