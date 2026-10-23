import pytest

from rapidreach.alerts import AlertRules, compute_alerts, new_alerts, persistent_gaps
from rapidreach.hazards import FireHazard, FloodHazard, GenericIncident, merge_effects
from rapidreach.pipeline import evaluate
from rapidreach.preposition import apply_moves, rank_staging_sites, recommend_moves
from rapidreach.response_stub import StubResponseEngine
from rapidreach.roadstate import road_state
from rapidreach.scenario import ScenarioPlayer, load_scenarios
from rapidreach.toy_graph import Asset, TARGETS_S, build_toy_graph, default_assets, node_id
from rapidreach.traffic import congestion_factor, time_multiplier

G, ENG, A = build_toy_graph(), StubResponseEngine(), default_assets()
SC = load_scenarios("scenarios")["Compound event: monsoon + fire + collapse"]


# ---- time of day -------------------------------------------------------------------------
def test_time_of_day_multipliers():
    assert congestion_factor(18) == 1.3 and congestion_factor(3) == 1.0 and congestion_factor(7) == 1.15
    assert time_multiplier(18, "arterial") == pytest.approx(1.3)
    assert time_multiplier(18, "local") == pytest.approx(1.15)
    assert time_multiplier(3, "local") == 1.0


def test_road_state_hour_scales_travel_time():
    e = next(iter(G.edges))
    night, peak = road_state(G, hour=3), road_state(G, hour=18)
    assert night.edges[e]["travel_time_s"] == pytest.approx(G.edges[e]["base_time_s"])
    assert peak.edges[e]["travel_time_s"] > night.edges[e]["travel_time_s"]


# ---- flood extent ------------------------------------------------------------------------
def test_flooded_nodes_reported_and_merged_by_max():
    a, b = FloodHazard(50).apply(G), FloodHazard(70).apply(G)
    assert a.flooded_nodes and all(d > 0 for d in a.flooded_nodes.values())
    m = merge_effects([a, b])
    assert all(m.flooded_nodes[n] == max(a.flooded_nodes.get(n, 0), b.flooded_nodes.get(n, 0)) for n in m.flooded_nodes)


# ---- routes ------------------------------------------------------------------------------
def test_assignment_paths_connect_unit_base_to_incident():
    eff = FireHazard(node_id(5, 2), 1).apply(G)       # sev 1: no cordon
    asg = ENG.dispatch(road_state(G, eff, hour=18), eff.incidents, A)
    assert asg
    for a in asg:
        assert a.path[0] == next(x.node for x in A if x.id == a.asset_id)
        assert a.path[-1] == node_id(5, 2) and not a.staged


def test_cordoned_incident_marks_staged_route():
    eff = FireHazard(node_id(4, 3), 2).apply(G)
    asg = ENG.dispatch(road_state(G, eff), eff.incidents, A)
    assert any(a.staged and a.path[-1] != node_id(4, 3) for a in asg)


# ---- free vs committed crews -------------------------------------------------------------
def test_committed_crews_do_not_count_toward_coverage():
    eff = merge_effects([GenericIncident("building_collapse", node=node_id(1, 5)).apply(G)])
    ev = evaluate(G, A, eff, ENG, hour=18)
    assert ev.committed and len(ev.free_assets) == len(A) - len(ev.committed)
    # the only rescue unit is out on the collapse -> no rescue coverage anywhere
    assert all(ev.cov[w]["rescue"] == 0 for w in ev.cov)
    assert all(ev.cov[w]["rescue"] >= 0 for w in ev.cov0) and any(ev.cov0[w]["rescue"] > 0 for w in ev.cov0)


def test_no_incidents_means_all_crews_free_and_cov_equals_baseline():
    ev = evaluate(G, A, merge_effects([]), ENG, hour=18)
    assert not ev.committed and ev.cov == ev.cov0


# ---- alerts ------------------------------------------------------------------------------
def test_no_alert_when_nothing_degrades():
    ev = evaluate(G, A, merge_effects([]), ENG, hour=18)
    assert compute_alerts(ev.assignments, ev.cov, ev.cov0) == []


def test_persistent_planning_gaps_are_not_live_alerts():
    ev = evaluate(G, A, merge_effects([]), ENG, hour=18)
    assert persistent_gaps(ev.cov0)             # the toy baseline has real gaps (W1 rescue, W7 ambulance, ...)
    assert not [a for a in compute_alerts(ev.assignments, ev.cov, ev.cov0) if a.kind == "ward"]


def test_degradation_raises_breach_and_ward_alerts():
    ev = evaluate(G, A, ScenarioPlayer(SC, G).effect_at(60), ENG, hour=18)
    al = compute_alerts(ev.assignments, ev.cov, ev.cov0)
    kinds = {(a.kind, a.level) for a in al}
    assert ("breach", "error") in kinds and ("ward", "warning") in kinds
    assert len({a.key for a in al}) == len(al)                  # keys unique even for repeated unit types


def test_alert_thresholds_are_configurable():
    ev = evaluate(G, A, ScenarioPlayer(SC, G).effect_at(60), ENG, hour=18)
    strict = compute_alerts(ev.assignments, ev.cov, ev.cov0, AlertRules(0.99, 0.01))
    lax = compute_alerts(ev.assignments, ev.cov, ev.cov0, AlertRules(0.05, 0.95))
    n = lambda al: sum(len(a.wards) for a in al if a.kind == "ward")
    assert n(strict) > n(lax)


def test_new_alerts_are_those_absent_at_previous_step():
    p = ScenarioPlayer(SC, G)
    now = evaluate(G, A, p.effect_at(55), ENG, 18); prev = evaluate(G, A, p.effect_at(50), ENG, 18)
    a_now = compute_alerts(now.assignments, now.cov, now.cov0)
    a_prev = compute_alerts(prev.assignments, prev.cov, prev.cov0)
    fresh = new_alerts(a_now, a_prev)
    assert any("FIRE-31" in k for k in fresh)
    assert not any(k in {a.key for a in a_prev} for k in fresh)
    assert new_alerts(a_now, None) == {a.key for a in a_now}


# ---- pre-positioning ---------------------------------------------------------------------
def test_recommend_moves_improves_coverage_for_badly_placed_unit():
    H = road_state(G, hour=18)
    assets = [Asset("AMB-X", "ambulance", node_id(0, 0))]
    moves = recommend_moves(H, assets)
    assert moves and moves[0].to_node != node_id(0, 0)
    assert moves[0].city_after > moves[0].city_before
    moved = apply_moves(assets, moves)
    cov_before = ENG.coverage(H, assets)
    cov_after = ENG.coverage(H, moved)
    assert sum(v["ambulance"] for v in cov_after.values()) > sum(v["ambulance"] for v in cov_before.values())


def test_recommend_moves_only_uses_free_units_and_is_deterministic():
    ev = evaluate(G, A, ScenarioPlayer(SC, G).effect_at(45), ENG, 18)
    m1, m2 = recommend_moves(ev.H, ev.free_assets), recommend_moves(ev.H, ev.free_assets)
    assert m1 == m2
    assert all(m.asset_id not in ev.committed for m in m1)
    assert all(m.city_after >= m.city_before for m in m1)


def test_no_free_units_means_no_recommendation():
    assert recommend_moves(road_state(G), []) == []


def test_rank_staging_sites_sorted_by_gain():
    H = road_state(G, hour=18)
    sites = rank_staging_sites(H, A, "ambulance", TARGETS_S, top_k=5)
    assert sites == sorted(sites, key=lambda s: (-s.newly_covered, s.node))
    assert all(s.city_after > s.city_before for s in sites)


# ---- scenario helpers --------------------------------------------------------------------
def test_scenario_event_times_and_source_label():
    assert SC.event_times() == [0, 20, 40, 55]
    assert "synthetic" in SC.source


def test_ward_alerts_are_grouped_per_service():
    ev = evaluate(G, A, ScenarioPlayer(SC, G).effect_at(60), ENG, hour=18)
    ward = [a for a in compute_alerts(ev.assignments, ev.cov, ev.cov0) if a.kind == "ward"]
    assert len({a.message.split()[0] for a in ward}) == len(ward) <= 3          # at most one per service
    assert all(len(a.wards) >= 1 for a in ward)
