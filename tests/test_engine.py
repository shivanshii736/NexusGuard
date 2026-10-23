import math, random
from nexusguard.engine import (AlertEngine, EngineSession, Incident, RoadState, Unit, compute_coverage,
                               dispatch, eta, providers_from_stations, recommend_prepositioning,
                               units_from_stations, rank_staging_sites, apply_plan)
from tests.engine_fixtures import TARGETS, grid, stations, wards


def wall():
    """Close every edge crossing between row 3 and row 4 (both directions)."""
    e = set()
    for c in range(7):
        e |= {((3, c), (4, c)), ((4, c), (3, c))}
    return RoadState(closed=frozenset(e))


def test_eta_and_closure():
    G = grid()
    assert eta(G, (0, 0), (1, 1)) == 120.0
    assert eta(G, (0, 0), (6, 0)) == 360.0
    assert eta(G, (0, 0), (6, 0), wall()) == math.inf
    slow = RoadState(slow={((0, 0), (0, 1)): 5.0})
    assert eta(G, (0, 0), (0, 1), slow) == 180.0   # detour via (1,0),(1,1) beats the 5x slowed block


def test_baseline_coverage_and_degradation():
    G, W, S = grid(), wards(), stations()
    base = compute_coverage(G, W, providers_from_stations(S), TARGETS)
    amb = base[base.service == "ambulance"].set_index("ward_id")
    assert amb.loc["w11", "eta_s"] == 120.0 and amb.loc["w11", "covered"]
    hit = compute_coverage(G, W, providers_from_stations(S), TARGETS, wall())
    fire, fire2 = (d[d.service == "fire"].set_index("ward_id") for d in (base, hit))
    assert fire.loc["w53", "eta_s"] == 120.0 and fire.loc["w53", "covered"]
    assert fire2.loc["w53", "eta_s"] == math.inf and not fire2.loc["w53", "covered"]


def test_contention_severity_wins_and_delay():
    G = grid()
    units = [Unit("a1", "ambulance", (0, 0))]
    inc = [Incident("low", "medical", (1, 1), severity=1), Incident("high", "medical", (0, 2), severity=4)]
    for policy in ("optimal", "greedy"):
        r = dispatch(G, inc, units, policy=policy)
        assert [a.incident_id for a in r.assignments] == ["high"]
        assert r.unmet == [("low", "ambulance")]
        assert r.units[0].busy_with == "high" and r.units[0].available_at > 0
        assert r.assignments[0].delay_s == 0.0
        # crew is committed -> a second call at the same time cannot reuse it
        r2 = dispatch(G, inc, r.units, now=0.0, policy=policy)
        assert not r2.assignments and len(r2.unmet) == 2


def test_contention_delay_reported():
    G = grid()
    units = [Unit("a1", "ambulance", (0, 0)), Unit("a2", "ambulance", (6, 6))]
    inc = [Incident("i1", "medical", (0, 1), severity=3), Incident("i2", "medical", (0, 2), severity=3)]
    r = dispatch(G, inc, units)
    assert len(r.assignments) == 2 and not r.unmet
    assert max(a.delay_s for a in r.assignments) > 0      # one incident loses its nearest crew


def test_optimal_never_worse_than_greedy():
    G = grid()
    rnd = random.Random(7)
    nodes = list(G.nodes)
    for _ in range(25):
        units = [Unit(f"u{i}", "ambulance", rnd.choice(nodes)) for i in range(4)]
        inc = [Incident(f"i{i}", "medical", rnd.choice(nodes), severity=rnd.randint(1, 5)) for i in range(4)]
        o, g = dispatch(G, inc, units, policy="optimal"), dispatch(G, inc, units, policy="greedy")
        assert len(o.assignments) >= len(g.assignments)
        assert o.total_weighted_eta(inc) <= g.total_weighted_eta(inc) + 1e-6


def test_multi_service_incident_and_unreachable():
    G, S = grid(), stations()
    units = units_from_stations(S)
    r = dispatch(G, [Incident("f1", "fire", (3, 4))], units)
    assert {a.service for a in r.assignments} == {"fire", "ambulance"}
    r = dispatch(G, [Incident("x", "medical", (6, 0))], [Unit("a", "ambulance", (0, 0))], wall())
    assert r.unmet == [("x", "ambulance")]


def test_preposition_improves_coverage():
    G, W = grid(), wards()
    units = [Unit("a1", "ambulance", (0, 0)), Unit("a2", "ambulance", (0, 1)), Unit("a3", "ambulance", (1, 0))]
    plan = recommend_prepositioning(G, W, units, TARGETS, services=("ambulance",), max_moves=2)
    assert plan.moves
    b = plan.summary_before.set_index("service").loc["ambulance", "wards_covered"]
    a = plan.summary_after.set_index("service").loc["ambulance", "wards_covered"]
    assert a > b
    assert any(m.unit_id for m in plan.moves) and len(apply_plan(units, plan)) == 3
    assert plan.comparison()["newly_covered"].any()
    ranked = rank_staging_sites(G, W, units, "ambulance", TARGETS)
    assert not ranked.empty and ranked.population_gained.is_monotonic_decreasing


def test_alerts_only_on_degradation():
    G, W, S = grid(), wards(), stations()
    s = EngineSession(G, W, S, TARGETS)
    quiet = s.update(None, [])
    assert quiet.alerts == []
    bad = s.update(wall(), [])
    assert bad.alerts, "closures should degrade something"
    again = s.update(wall(), [])
    assert again.alerts == []                       # deduped, nothing new
    snap = EngineSession(G, W, S, TARGETS).update(None, [Incident("a", "medical", (6, 0), 2), Incident("b", "medical", (6, 1), 2),
                                                          Incident("c", "medical", (6, 2), 2)])
    assert any(a.code == "INCIDENT_UNSERVED" for a in snap.alerts)   # 2 ambulances, 3 incidents


def test_compound_event_session():
    G, W, S = grid(), wards(), stations()
    s = EngineSession(G, W, S, TARGETS)
    snap = s.update(wall(), [Incident("fire", "fire", (2, 2), 4), Incident("collapse", "generic", (5, 5), 5)])
    assert snap.dispatch.assignments
    plan = s.preposition(wall())
    assert plan.before is not None and plan.after is not None
