# NexusGuard: one engine, multiple hazards

Emergency-response accessibility for Bengaluru. Flood and fire plug-ins turn hazard events into road closures,
slowdowns and incidents; one shared engine computes ward-level response coverage (ambulance / fire / rescue),
models competing incidents for limited crews, and recommends where to pre-position vehicles.

**Honest limits (say these in the demo):** traffic multipliers are ASSUMED; hospitals are PROXIES for non-public
ambulance bases; no live traffic or real dispatch data.

## Run
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q          # 66 tests, toy graph, no downloads
streamlit run app.py
```
Rebuilding the real OSM graph needs `pip install -r requirements.osm.txt` and internet (Overpass).

## Layout
| Path | What |
|---|---|
| `app.py` | Streamlit entry point (Planning / Live scenario replay / Live manual incidents) |
| `nexusguard/types.py` | shared contract for the real (OSM) pipeline |
| `nexusguard/config.py` | all tunables; anything marked ASSUMED must be labelled as such in UI and deck |
| `nexusguard/network/` | OSM graph, peak multipliers, assets, wards, planning baseline, adapters |
| `nexusguard/engine/` | ETAs, coverage, crew dispatch (contention), pre-positioning, alerts (networkx MultiDiGraph) |
| `nexusguard/hazards/` | flood, fire, generic incident plug-ins -> `HazardEffect` |
| `nexusguard/scenario.py`, `scenarios/` | timeline replay + JSON scenarios |
| `nexusguard/live/` | the live-mode stack the app runs on today: road-state, stub dispatch, alerts, pre-positioning |
| `nexusguard/toy_graph.py`, `traffic.py`, `geo.py` | 7x7 demo city (with elevation/wards), time-of-day multipliers, haversine |
| `nexusguard/ui/maps.py` | Folium map builder |
| `tests/` | `toy_graph.py` / `engine_fixtures.py` = synthetic cities used by the tests |

> Known architecture debt: the app currently runs on `nexusguard/live/` (nx.Graph toy city), while
> `nexusguard/engine/` + `network/` target the real OSM MultiDiGraph. Unifying them is the next milestone.

## Git rules
- `main` always runs (`pytest -q` green). Small PRs.
- Never commit large data. Share the cached graph via a drive link; the demo must work offline.
