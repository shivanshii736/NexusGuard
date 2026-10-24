"""Folium map for the live picture: ward coverage, roads (closed / slowed), flood depth, routes,
crews, incidents and proposed staging. Only closed/slowed edges are styled loudly; the rest is a faint grid."""
from __future__ import annotations
import folium

from nexusguard.toy_graph import edge_key

SERVICE_COLOUR = {"ambulance": "green", "fire": "red", "rescue": "blue"}
SERVICE_HEX = {"ambulance": "#2e9e5b", "fire": "#d64545", "rescue": "#2f6fd6"}
INCIDENT_ICON = {"fire": "fire", "flood_rescue": "tint", "building_collapse": "home",
                 "lake_breach": "tint", "road_accident": "road", "other": "exclamation-sign"}
SEVERE_SLOWDOWN = 1.8     # a road slowed at least this much counts as "severely slowed"


def _coords(G, n: int) -> list[float]:
    return [G.nodes[n]["lat"], G.nodes[n]["lon"]]


def build_map(G, assets, ev, effect, moves, rules) -> folium.Map:
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
        pts = [_coords(G, u), _coords(G, v)]
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
        folium.CircleMarker(_coords(G, n), radius=2, color="#44506a", fill=True,
                            tooltip=f"{d['label']} · elev {d['elevation']} m").add_to(g_roads)

    for n, depth in effect.flooded_nodes.items():
        folium.CircleMarker(_coords(G, n), radius=6 + 14 * depth, color="#2f6fd6", weight=1, fill=True,
                            fill_opacity=0.35, tooltip=f"water {depth:.2f} m").add_to(g_flood)

    inc_node = {i.id: i.node for i in effect.incidents}
    for a in ev.assignments:
        if a.asset_id and a.path:
            pts = [_coords(G, n) for n in a.path] + ([_coords(G, inc_node[a.incident_id])] if a.staged else [])
            tag = "BREACH " if a.breach else ""
            folium.PolyLine(pts, color=SERVICE_HEX[a.service], weight=5, opacity=0.9,
                            dash_array="2 8" if a.breach else None,
                            tooltip=f"{tag}{a.asset_id} → {a.incident_id}: {a.eta_s / 60:.1f} min "
                                    f"(target {a.target_s / 60:.0f})").add_to(g_routes)

    inc_for = {a.asset_id: a for a in ev.assignments if a.asset_id}
    for a in assets:
        busy = inc_for.get(a.id)
        note = " (hospital proxy)" if a.service == "ambulance" else ""
        status = f"committed to {busy.incident_id}" if busy else "free"
        folium.Marker(_coords(G, a.node), tooltip=f"{a.id}{note} · {status}",
                      icon=folium.Icon(color="gray" if busy else SERVICE_COLOUR[a.service],
                                       icon="plus-sign" if a.service == "ambulance" else "road",
                                       prefix="glyphicon")).add_to(g_crews)
    for inc in effect.incidents:
        folium.Marker(_coords(G, inc.node), tooltip=inc.label, popup=f"{inc.label}<br>needs {inc.required_units}",
                      icon=folium.Icon(color="black", icon=INCIDENT_ICON.get(inc.kind, "exclamation-sign"),
                                       prefix="glyphicon")).add_to(g_inc)
    for mv in moves:
        folium.PolyLine([_coords(G, mv.from_node), _coords(G, mv.to_node)], color="#7a3fd0", weight=3,
                        dash_array="8 6").add_to(g_prop)
        folium.Marker(_coords(G, mv.to_node), tooltip=f"Pre-position {mv.asset_id} here",
                      icon=folium.Icon(color="purple", icon="flag", prefix="glyphicon")).add_to(g_prop)
    folium.LayerControl(collapsed=True).add_to(m)
    return m
