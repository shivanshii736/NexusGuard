from pathlib import Path
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")
PLANNING, REPLAY, MANUAL = "Planning · baseline", "Live · scenario replay", "Live · manual incidents"


def run(mode=PLANNING):
    at = AppTest.from_file(APP, default_timeout=90).run()
    at.sidebar.radio(key="mode").set_value(mode).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def metrics(at):
    return dict(zip(["closed", "slowed", "incidents", "breaches", "free", "worst"], [m.value for m in at.metric]))


def test_planning_mode_has_no_incidents_and_lists_findings():
    at = run()
    m = metrics(at)
    assert (m["closed"], m["incidents"], m["breaches"], m["free"]) == ("0", "0", "0", "6/6")
    assert any("coverage" in w.value for w in at.warning)          # persistent planning gaps are shown


def test_planning_mode_recommends_prepositioning():
    at = run()
    assert any(s.value == "🎯 Recommended pre-positioning" for s in at.subheader)


def _new(at):
    return [e.value for e in list(at.error) + list(at.warning) if e.icon == "🆕"]


def test_replay_degrades_over_time_and_flags_only_new_alerts():
    at = run(REPLAY)
    at.sidebar.slider(key="t_now").set_value(55).run()           # fire starts at t=55
    assert not at.exception
    m = metrics(at)
    assert int(m["closed"]) > 0 and m["incidents"] == "3" and int(m["breaches"]) > 0
    assert any("FIRE-31" in v for v in _new(at))
    at.sidebar.slider(key="t_now").set_value(60).run()           # nothing new since t=55
    assert not any("FIRE-31" in v for v in _new(at))


def test_next_event_button_jumps_to_event_time():
    at = run(REPLAY)
    at.sidebar.button(key="next_ev").click().run()
    assert at.sidebar.slider(key="t_now").value == 20
    at.sidebar.button(key="next_ev").click().run()
    assert at.sidebar.slider(key="t_now").value == 40
    at.sidebar.button(key="prev_ev").click().run()
    assert at.sidebar.slider(key="t_now").value == 20 and not at.exception


def test_manual_mode_add_fire_and_clear():
    at = run(MANUAL)
    assert any("No response-time" in s.value or "Monitoring" in s.value for s in at.success)
    at.sidebar.select_slider(key="fire_s").set_value(3)
    at.sidebar.button(key="add_fire").click().run()
    assert not at.exception and metrics(at)["incidents"] == "1" and int(metrics(at)["closed"]) > 0
    at.sidebar.button(key="clear_manual").click().run()
    assert metrics(at)["incidents"] == "0"


def test_manual_flood_and_generic_incident():
    at = run(MANUAL)
    at.sidebar.toggle(key="flood_on").set_value(True).run()
    at.sidebar.slider(key="rain").set_value(70).run()
    at.sidebar.button(key="add_gen").click().run()
    assert not at.exception and int(metrics(at)["incidents"]) >= 2


def _etas(at):
    df = next(d.value for d in at.dataframe if "ETA (min)" in d.value.columns)
    return df["ETA (min)"].dropna().tolist()


def test_time_of_day_changes_eta():
    at = run(MANUAL)
    at.sidebar.button(key="add_fire").click().run()
    at.sidebar.slider(key="hour").set_value(18).run()
    peak = _etas(at)
    at.sidebar.slider(key="hour").set_value(3).run()
    night = _etas(at)
    assert not at.exception and peak and sum(peak) > sum(night)
