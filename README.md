# RapidReach: one engine, multiple hazards

Emergency-response accessibility for Bengaluru. Flood and fire plug-ins turn hazard events into road closures,
slowdowns and incidents; one shared engine computes ward-level response coverage (ambulance / fire / rescue),
models competing incidents for limited crews, and recommends where to pre-position vehicles.

**Honest limits (say these in the demo):** traffic multipliers are ASSUMED; hospitals are PROXIES for non-public
ambulance bases; no live traffic or real dispatch data.

## Run
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q          # works on the toy graph, no downloads
streamlit run app.py
```

## Layout and owners
| Path | Owner | What |
|---|---|---|
| `rapidreach/types.py` | ALL | shared contract; change only by agreement |
| `rapidreach/network/`, `data/` | P1 | OSM graph, peak multipliers, assets, wards, planning-mode baseline |
| `rapidreach/engine/` | P2 | ETAs, coverage, crew dispatch (contention), pre-positioning, alerts |
| `rapidreach/hazards/`, `scenarios/` | P3 | flood, fire, generic incidents, Oct 2024 / May 2025 replays |
| `rapidreach/ui/`, `app.py` | P3 | Streamlit + Folium |
| `tests/toy_graph.py` | ALL | synthetic 7x7 city: develop against this first |

## Git rules
- `main` always runs. Work on `p1/...`, `p2/...`, `p3/...` branches; small PRs; merge at least every ~90 min.
- Stay inside your own folders; touch `types.py` only after a quick huddle.
- Never commit large data. Share the cached graph via a drive link; the demo must work offline.
