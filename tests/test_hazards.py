import networkx as nx
import pytest

from nexusguard.hazards import FireHazard, FloodHazard, GenericIncident, hazard_from_dict, merge_effects
from nexusguard.live.roadstate import road_state
from nexusguard.live.response_stub import StubResponseEngine
from nexusguard.scenario import Scenario, ScenarioPlayer, load_scenarios
from nexusguard.toy_graph import build_toy_graph, default_assets, edge_key, node_id

G = build_toy_graph()


def test_flood_no_rain_no_effect():
    eff = FloodHazard(rainfall_mm_hr=10, drainage_mm_hr=20).apply(G)
    assert not eff.closed_edges and not eff.slowdowns and not eff.incidents


def test_flood_monotonic_and_underpass_first():
    closed = [len(FloodHazard(rainfall_mm_hr=r).apply(G).closed_edges) for r in (30, 40, 50, 60, 80)]
    assert closed == sorted(closed) and closed[-1] > closed[0]
    # underpass closes at lower depth than a normal road at the same elevation
    eff = FloodHazard(rainfall_mm_hr=40).apply(G)       # level 0.4 m
    assert edge_key(node_id(2, 3), node_id(3, 3)) in eff.closed_edges


def test_flood_raises_rescue_incident_in_basin():
    eff = FloodHazard(rainfall_mm_hr=60).apply(G)
    assert eff.incidents and eff.incidents[0].required_units["rescue"] == 1


@pytest.mark.parametrize("sev,min_closed", [(1, 0), (2, 1), (3, 4)])
def test_fire_footprint_grows_with_severity(sev, min_closed):
    eff = FireHazard(node_id(4, 4), sev).apply(G)
    assert len(eff.closed_edges) >= min_closed
    assert eff.incidents[0].kind == "fire"


def test_fire_rejects_bad_severity():
    with pytest.raises(ValueError):
        FireHazard(0, 9)


def test_generic_snaps_latlon_to_nearest_node():
    n = G.nodes[node_id(3, 3)]
    eff = GenericIncident("building_collapse", lat=n["lat"] + 1e-4, lon=n["lon"] - 1e-4).apply(G)
    assert eff.incidents[0].node == node_id(3, 3)


def test_generic_needs_location_and_known_kind():
    with pytest.raises(ValueError):
        GenericIncident("other")
    with pytest.raises(ValueError):
        GenericIncident("meteor", node=1)


def test_roundtrip_serialisation():
    for h in (FloodHazard(55, 3), FireHazard(5, 3), GenericIncident("lake_breach", node=9)):
        h2 = hazard_from_dict(h.to_dict())
        assert h2.to_dict() == h.to_dict()


def test_merge_closure_wins_over_slowdown_and_dedupes_incidents():
    a = FloodHazard(60).apply(G)
    b = FloodHazard(60).apply(G)
    m = merge_effects([a, b])
    assert not (set(m.slowdowns) & m.closed_edges)
    assert len({i.id for i in m.incidents}) == len(m.incidents)


def test_road_state_removes_closed_and_scales_time():
    eff = FireHazard(node_id(3, 3), 3).apply(G)
    H = road_state(G, eff)
    assert all(not H.has_edge(*e) for e in eff.closed_edges)
    assert G.number_of_edges() - H.number_of_edges() == len(eff.closed_edges)   # base graph untouched
    slowed = next(iter(eff.slowdowns))
    assert H.edges[slowed]["travel_time_s"] == pytest.approx(G.edges[slowed]["base_time_s"] * eff.slowdowns[slowed])


def test_cordoned_incident_is_still_reachable_via_staging():
    eff = FireHazard(node_id(4, 3), 2).apply(G)
    H = road_state(G, eff)
    asg = StubResponseEngine().dispatch(H, eff.incidents, default_assets())
    assert any(a.asset_id for a in asg)


def test_contention_exhausts_single_rescue_unit():
    eff = merge_effects([GenericIncident("building_collapse", node=node_id(1, 5)).apply(G),
                         GenericIncident("lake_breach", node=node_id(5, 1)).apply(G)])
    asg = StubResponseEngine().dispatch(road_state(G, eff), eff.incidents, default_assets())
    rescue = [a for a in asg if a.service == "rescue"]
    assert len(rescue) == 4 and sum(a.asset_id is not None for a in rescue) == 1


def test_baseline_coverage_in_unit_range_and_hazard_never_improves_it():
    eng, A = StubResponseEngine(), default_assets()
    base = eng.coverage(road_state(G), A)
    eff = merge_effects([FloodHazard(70).apply(G)])
    hit = eng.coverage(road_state(G, eff), A)
    for w in base:
        for s in base[w]:
            assert 0 <= hit[w][s] <= base[w][s] <= 1


def test_scenario_replay_is_time_gated_and_deterministic():
    sc = load_scenarios("scenarios")["Compound event: monsoon + fire + collapse"]
    p = ScenarioPlayer(sc, G)
    kinds = lambda t: sorted(i.kind for i in p.effect_at(t).incidents)
    assert kinds(0) == ["flood_rescue"]
    assert "building_collapse" in kinds(45) and "fire" not in kinds(45)
    assert "fire" in kinds(60)
    assert p.effect_at(60).closed_edges == p.effect_at(60).closed_edges
    # incident start times come from the event time
    assert {i.kind: i.t_start_min for i in p.effect_at(60).incidents}["fire"] == 55


def test_scenario_json_roundtrip():
    sc = load_scenarios("scenarios")["Peak-hour fire (no flood)"]
    assert Scenario.from_dict(sc.to_dict()).to_dict() == sc.to_dict()
