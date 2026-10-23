"""RapidReach - Streamlit app shell (P3).  Run:  streamlit run app.py"""
from __future__ import annotations
from pathlib import Path
import folium
import pandas as pd
import streamlit as st

from rapidreach.alerts import AlertRules, compute_alerts, new_alerts, persistent_gaps
from rapidreach.hazards import FireHazard, FloodHazard, GenericIncident, GENERIC_PRESETS, hazard_from_dict, merge_effects
from rapidreach.pipeline import evaluate
from rapidreach.preposition import apply_moves, rank_staging_sites, recommend_moves
from rapidreach.scenario import ScenarioPlayer, load_scenarios
from rapidreach.toy_graph import TARGETS_S, build_toy_graph, default_assets, edge_key
from rapidreach.traffic import congestion_factor, time_multiplier
# P1/P2: swap this import for the real shared engine (same coverage()/dispatch() interface)
from rapidreach.response_stub import StubResponseEngine as Engine

try:
    from streamlit_folium import st_folium
except ImportError:          # fallback keeps the app usable without the extra package
    st_folium = None

PLANNING, REPLAY, MANUAL = "Planning · baseline", "Live · scenario replay", "Live · manual incidents"
SERVICE_COLOUR = {"ambulance": "green", "fire": "red", "rescue": "blue"}
SERVICE_HEX = {"ambulance": "#2e9e5b", "fire": "#d64545", "rescue": "#2f6fd6"}
INCIDENT_ICON = {"fire": "fire", "flood_rescue": "tint", "building_collapse": "home",
                 "lake_breach": "tint", "road_accident": "road", "other": "exclamation-sign"}
SEVERE_SLOWDOWN = 1.8     # a road slowed at least this much counts as "severely slowed"
PREV_STEP_MIN = 5         # live alerts are "new" relative to the state this many minutes earlier

st.set_page_config(page_title="RapidReach", page_icon="🚒", layout="wide")


@st.cache_resource
def get_world():
    return build_toy_graph(), default_assets(), load_scenarios(Path(__file__).parent / "scenarios")


G, ASSETS, SCENARIOS = get_world()
ENGINE = Engine()
NODE_LABELS = {n: f"{n} {d['label']} · {d['ward']}" for n, d in G.nodes(data=True)}
ASSET_BY_ID = {a.id: a for a in ASSETS}
st.session_state.setdefault("manual", [])


def _coords(n: int) -> list[float]:
    return [G.nodes[n]["lat"], G.nodes[n]["lon"]]


def _jump(t: float):
    st.session_state["t_now"] = int(t)


# ───────────────────────────── sidebar ─────────────────────────────
st.sidebar.title("🚒 RapidReach")
mode = st.sidebar.radio("Mode", [PLANNING, REPLAY, MANUAL], key="mode")
hour = st.sidebar.slider("Time of day (h)", 0, 23, 18, key="hour",
                         help="Assumed time-of-day speed multipliers, not measured traffic.")
st.sidebar.caption(f"Assumed travel-time x: arterial {time_multiplier(hour, 'arterial'):.2f} · "
                   f"local {time_multiplier(hour, 'local'):.2f}"
                   + (" (peak)" if congestion_factor(hour) >= 1.3 else ""))

with st.sidebar.expander("Alert rules"):
    ward_thr = st.slider("Ward under-served below (% nodes within target)", 50, 100, 80, key="ward_thr")
    min_drop = st.slider("Alert when coverage drops by at least (pts)", 5, 50, 10, key="min_drop")
rules = AlertRules(ward_thr / 100, min_drop / 100)

with st.sidebar.expander("Assumptions & limitations"):
    st.markdown(
        "- Toy road graph; OSM graph plugs in via P1.\n"
        "- Traffic multipliers, flood depths, fire/collapse radii and response targets are **assumptions**.\n"
        "- Hospitals are **provisional ambulance-base proxies**; real vehicle bases are not public.\n"
        "- Dispatch is a simple greedy stand-in. **No claim of verified live traffic or operational dispatch accuracy.**")

hazards, player, sc, t_now = [], None, None, 0
if mode == REPLAY:
    sc = SCENARIOS[st.sidebar.selectbox("Scenario", list(SCENARIOS), key="scenario")]
    if st.session_state.get("t_now", 0) > sc.duration_min:
        st.session_state["t_now"] = 0
    st.session_state.setdefault("t_now", 0)
    st.sidebar.caption(sc.description)
    st.sidebar.caption(f"Source: {sc.source}")
    t_now = st.sidebar.slider("Scenario time (min)", 0, int(sc.duration_min), key="t_now")
    times = sc.event_times()
    prev_t = max([x for x in times if x < t_now], default=None)
    next_t = min([x for x in times if x > t_now], default=None)
    b1, b2 = st.sidebar.columns(2)
    b1.button("◀ Prev event", disabled=prev_t is None, on_click=_jump, args=(prev_t or 0,), key="prev_ev")
    b2.button("Next event ▶", disabled=next_t is None, on_click=_jump, args=(next_t or 0,), key="next_ev")
    player = ScenarioPlayer(sc, G)
elif mode == MANUAL:
    with st.sidebar.expander("🌧️ Flood", expanded=True):
        if st.toggle("Enable flood", value=False, key="flood_on"):
            rain = st.slider("Rainfall (mm/hr)", 0, 120, 50, key="rain")
            dur = st.slider("Duration (h)", 0.5, 6.0, 2.0, 0.5, key="dur")
            hazards.append(FloodHazard(rainfall_mm_hr=rain, duration_h=dur))
    with st.sidebar.expander("🔥 Add fire"):
        n = st.selectbox("Location", list(NODE_LABELS), format_func=NODE_LABELS.get, key="fire_n")
        sev = st.select_slider("Severity", [1, 2, 3], 2, key="fire_s")
        if st.button("Add fire", key="add_fire"):
            st.session_state.manual.append(FireHazard(n, sev).to_dict())
    with st.sidebar.expander("⚠️ Add generic incident"):
        kind = st.selectbox("Kind", list(GENERIC_PRESETS), format_func=lambda k: k.replace("_", " ").title(), key="gen_k")
        n = st.selectbox("Location", list(NODE_LABELS), format_func=NODE_LABELS.get, key="gen_n")
        sev = st.select_slider("Severity", [1, 2, 3], 2, key="gen_s")
        if st.button("Add incident", key="add_gen"):
            st.session_state.manual.append(GenericIncident(kind, node=n, severity=sev).to_dict())
    hazards += [hazard_from_dict(h) for h in st.session_state.manual]
    if st.session_state.manual:
        st.sidebar.caption("Manual incidents: " + ", ".join(h.describe() for h in hazards[(1 if st.session_state.get("flood_on") else 0):]))
        if st.sidebar.button("Clear manual incidents", key="clear_manual"):
            st.session_state.manual = []
            st.rerun()

# ───────────────────────────── compute ─────────────────────────────
if mode == REPLAY:
    effect = player.effect_at(t_now)
    prev_ev = evaluate(G, ASSETS, player.effect_at(t_now - PREV_STEP_MIN), ENGINE, hour) if t_now > 0 else None
else:
    effect = merge_effects([h.apply(G) for h in hazards])
    prev_ev = None

ev = evaluate(G, ASSETS, effect, ENGINE, hour)
live = mode != PLANNING
alerts = compute_alerts(ev.assignments, ev.cov, ev.cov0, rules) if live else []
fresh = new_alerts(alerts, compute_alerts(prev_ev.assignments, prev_ev.cov, prev_ev.cov0, rules) if prev_ev else None) \
    if mode == REPLAY else set()

moves = recommend_moves(ev.H, ev.free_assets, TARGETS_S)
after_assets = apply_moves(ev.free_assets, moves)
cov_after = ENGINE.coverage(ev.H, after_assets, TARGETS_S)
gaps = persistent_gaps(ev.cov0, rules)

# ───────────────────────────── header + metrics ─────────────────────────────
st.title("RapidReach · one engine, multiple hazards")
st.caption(mode + (f" · t = {t_now} min" if mode == REPLAY else "") + f" · {hour:02d}:00 · toy graph")

severe = sum(m >= SEVERE_SLOWDOWN for m in effect.slowdowns.values())
worst0 = min(min(v.values()) for v in ev.cov0.values())
worst = min(min(v.values()) for v in ev.cov.values())
breaches = [a for a in ev.assignments if a.breach]
c = st.columns(6)
c[0].metric("Roads closed", len(effect.closed_edges))
c[1].metric("Roads slowed", len(effect.slowdowns), f"{severe} severe", delta_color="off")
c[2].metric("Active incidents", len(effect.incidents))
c[3].metric("Response breaches", len(breaches))
c[4].metric("Free crews", f"{len(ev.free_assets)}/{len(ASSETS)}")
c[5].metric("Worst ward coverage", f"{worst:.0%}", f"{worst - worst0:+.0%} vs baseline", delta_color="normal")

if sc:
    with st.expander("Scenario timeline", expanded=False):
        for t, label in player.timeline():
            st.write(("✅ " if t <= t_now else "⏳ ") + f"**t+{t:.0f} min** · {label}")
for note in effect.notes:
    st.caption("• " + note)


# ───────────────────────────── map ─────────────────────────────
def build_map() -> folium.Map:
    lat0 = sum(d["lat"] for _, d in G.nodes(data=True)) / G.number_of_nodes()
    lon0 = sum(d["lon"] for _, d in G.nodes(data=True)) / G.number_of_nodes()
    m = folium.Map(location=[lat0, lon0], zoom_start=14, tiles="OpenStreetMap")
    layer = lambda name, show=True: folium.FeatureGroup(name=name, show=show).add_to(m)
    g_wards, g_roads, g_flood = layer("Wards (coverage)"), layer("Roads"), layer("Flood depth")
    g_routes, g_crews, g_inc, g_prop = layer("Response routes"), layer("Crews / bases"), layer("Incidents"), layer("Proposed staging")

    by_ward: dict[str, list[dict]] = {}
    for _, d in G.nodes(data=True):
        by_ward.setdefault(d["ward"], []).append(d)
    for w, ds in by_ward.items():
        score = min(ev.cov[w].values())
        colour = "#2e9e5b" if score >= 0.9 else "#e0a526" if score >= rules.ward_threshold - 0.2 else "#d64545"
        b = [[min(d["lat"] for d in ds) - 0.0025, min(d["lon"] for d in ds) - 0.0027],
             [max(d["lat"] for d in ds) + 0.0025, max(d["lon"] for d in ds) + 0.0027]]
        tip = f"{w}: " + ", ".join(f"{s} {v:.0%}" for s, v in ev.cov[w].items())
        folium.Rectangle(b, color=colour, weight=1, fill=True, fill_opacity=0.14, tooltip=tip).add_to(g_wards)

    for u, v, d in G.edges(data=True):
        e = edge_key(u, v)
        pts = [_coords(u), _coords(v)]
        if e in effect.closed_edges:
            folium.PolyLine(pts, color="#d64545", weight=5, dash_array="6 6", tooltip="CLOSED").add_to(g_roads)
        elif e in effect.slowdowns:
            mult = effect.slowdowns[e]
            lab = "severely slowed" if mult >= SEVERE_SLOWDOWN else "slowed"
            folium.PolyLine(pts, color="#e08a1e", weight=4, tooltip=f"{lab} x{mult:.1f}").add_to(g_roads)
        else:
            folium.PolyLine(pts, color="#6b7a90", weight=3 if d["road_class"] == "arterial" else 2, opacity=0.7,
                            tooltip=f"{d['road_class']} · {d['base_speed_kph']} kph").add_to(g_roads)
    for n, d in G.nodes(data=True):
        folium.CircleMarker(_coords(n), radius=2, color="#44506a", fill=True,
                            tooltip=f"{d['label']} · elev {d['elevation']} m").add_to(g_roads)

    for n, depth in effect.flooded_nodes.items():
        folium.CircleMarker(_coords(n), radius=6 + 14 * depth, color="#2f6fd6", weight=1, fill=True,
                            fill_opacity=0.35, tooltip=f"water {depth:.2f} m").add_to(g_flood)

    inc_node = {i.id: i.node for i in effect.incidents}
    for a in ev.assignments:
        if a.asset_id and a.path:
            pts = [_coords(n) for n in a.path] + ([_coords(inc_node[a.incident_id])] if a.staged else [])
            tag = "BREACH " if a.breach else ""
            folium.PolyLine(pts, color=SERVICE_HEX[a.service], weight=5, opacity=0.9,
                            dash_array="2 8" if a.breach else None,
                            tooltip=f"{tag}{a.asset_id} → {a.incident_id}: {a.eta_s / 60:.1f} min "
                                    f"(target {a.target_s / 60:.0f})").add_to(g_routes)

    inc_for = {a.asset_id: a for a in ev.assignments if a.asset_id}
    for a in ASSETS:
        busy = inc_for.get(a.id)
        note = " (hospital proxy)" if a.service == "ambulance" else ""
        status = f"committed to {busy.incident_id}" if busy else "free"
        folium.Marker(_coords(a.node), tooltip=f"{a.id}{note} · {status}",
                      icon=folium.Icon(color="gray" if busy else SERVICE_COLOUR[a.service],
                                       icon="plus-sign" if a.service == "ambulance" else "road",
                                       prefix="glyphicon")).add_to(g_crews)
    for inc in effect.incidents:
        folium.Marker(_coords(inc.node), tooltip=inc.label, popup=f"{inc.label}<br>needs {inc.required_units}",
                      icon=folium.Icon(color="black", icon=INCIDENT_ICON.get(inc.kind, "exclamation-sign"),
                                       prefix="glyphicon")).add_to(g_inc)
    for mv in moves:
        folium.PolyLine([_coords(mv.from_node), _coords(mv.to_node)], color="#7a3fd0", weight=3,
                        dash_array="8 6").add_to(g_prop)
        folium.Marker(_coords(mv.to_node), tooltip=f"Pre-position {mv.asset_id} here",
                      icon=folium.Icon(color="purple", icon="flag", prefix="glyphicon")).add_to(g_prop)
    folium.LayerControl(collapsed=True).add_to(m)
    return m


left, right = st.columns([3, 2])
with left:
    m = build_map()
    if st_folium:
        st_folium(m, height=580, use_container_width=True, returned_objects=[])
    else:
        import streamlit.components.v1 as components
        components.html(m._repr_html_(), height=600)
    st.caption("Wards: green ≥90% of nodes within target · amber · red under-served. Red dashed = closed · orange = slowed. "
               "Coloured lines = unit → incident route (dotted = target missed). Grey pins = committed crews. Purple = proposed staging.")

with right:
    st.subheader("🚨 Alerts" if live else "📋 Planning findings")
    if live:
        if not alerts:
            st.success("Monitoring: no response-time or coverage degradation vs targets. No alert.")
        for a in alerts:
            (st.error if a.level == "error" else st.warning)(a.message, icon="🆕" if a.key in fresh else None)
    else:
        if not gaps:
            st.success(f"Every ward is at or above {rules.ward_threshold:.0%} coverage for all services at {hour:02d}:00.")
        for w, s, v in gaps:
            st.warning(f"{w}: {s} coverage {v:.0%} < {rules.ward_threshold:.0%} (target {TARGETS_S[s] // 60} min)")

    st.subheader("🎯 Recommended pre-positioning")
    if moves:
        st.dataframe(pd.DataFrame([{
            "unit": mv.asset_id, "move": f"{G.nodes[mv.from_node]['label']} → {G.nodes[mv.to_node]['label']}",
            "city coverage": f"{mv.city_before:.0%} → {mv.city_after:.0%}",
            "worst ward": f"{mv.worst_before:.0%} → {mv.worst_after:.0%}"} for mv in moves]),
            hide_index=True, width="stretch")
    elif not ev.free_assets:
        st.info("No free crews left to reposition.")
    else:
        st.info("No relocation of an available unit improves coverage.")
    if not live:
        with st.expander("Rank candidate staging sites (add one vehicle)"):
            rows = [{"service": s.service, "site": NODE_LABELS[s.node], "newly covered nodes": s.newly_covered,
                     "city coverage": f"{s.city_before:.0%} → {s.city_after:.0%}"}
                    for svc in TARGETS_S for s in rank_staging_sites(ev.H, ASSETS, svc, TARGETS_S, 3)]
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch") if rows else st.caption("Already full coverage.")

    st.subheader("Dispatch")
    if ev.assignments:
        st.dataframe(pd.DataFrame([{
            "incident": a.incident_id, "service": a.service, "unit": a.asset_id or "—",
            "ETA (min)": None if a.eta_s is None else round(a.eta_s / 60, 1),
            "target (min)": round(a.target_s / 60), "status": "⚠️ breach" if a.breach else "ok"}
            for a in ev.assignments]), hide_index=True, width="stretch")
    else:
        st.caption("Nothing to dispatch.")

# ───────────────────────────── tables ─────────────────────────────
st.subheader("Ward coverage (share of nodes within target)")
show_after = st.toggle("Show projected coverage after pre-positioning", value=bool(moves), key="show_after")
rows = []
for w in ev.cov:
    row = {"ward": w}
    for s in TARGETS_S:
        row[f"{s} · base"] = ev.cov0[w][s]
        row[f"{s} · now"] = ev.cov[w][s]
        if show_after:
            row[f"{s} · after"] = cov_after[w][s]
    rows.append(row)
df = pd.DataFrame(rows)
pct = [c for c in df.columns if c != "ward"]
styler = df.style.format("{:.0%}", subset=pct)
styler = styler.map(lambda v: "color:#d64545;font-weight:600" if isinstance(v, float) and v < rules.ward_threshold else "",
                    subset=pct)
st.dataframe(styler, hide_index=True, width="stretch")
st.caption("Targets: " + " · ".join(f"{s} {t // 60} min" for s, t in TARGETS_S.items())
           + f". Red = below {rules.ward_threshold:.0%}. base = no hazard, all crews at base; now = hazards applied and only "
             "crews not committed to an incident count; after = projected if the recommended crews are pre-positioned.")

c1, c2 = st.columns(2)
with c1:
    st.subheader("Crew status")
    inc_for = {a.asset_id: a for a in ev.assignments if a.asset_id}
    st.dataframe(pd.DataFrame([{
        "unit": a.id, "service": a.service, "base node": G.nodes[a.node]["label"] + (" (hospital proxy)" if a.service == "ambulance" else ""),
        "status": f"committed → {inc_for[a.id].incident_id}" if a.id in inc_for else "free"} for a in ASSETS]),
        hide_index=True, width="stretch")
with c2:
    st.subheader(f"Affected roads ({len(effect.closed_edges) + len(effect.slowdowns)})")
    road_rows = [{"road": f"{G.nodes[u]['label']}–{G.nodes[v]['label']}", "class": G.edges[u, v]["road_class"],
                  "status": "closed", "slowdown": "—"} for u, v in sorted(effect.closed_edges)]
    road_rows += [{"road": f"{G.nodes[u]['label']}–{G.nodes[v]['label']}", "class": G.edges[u, v]["road_class"],
                   "status": "severely slowed" if mlt >= SEVERE_SLOWDOWN else "slowed", "slowdown": f"x{mlt:.1f}"}
                  for (u, v), mlt in sorted(effect.slowdowns.items(), key=lambda kv: -kv[1])]
    st.dataframe(pd.DataFrame(road_rows), hide_index=True, width="stretch") if road_rows else st.caption("No closed or slowed roads.")
