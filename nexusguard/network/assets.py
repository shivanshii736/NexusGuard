"""PERSON 1. Response assets: hospitals (ambulance proxies) + fire stations (OSM merged with a hand-checked CSV)."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from nexusguard import config
from nexusguard.types import Asset
from nexusguard.network.snap import nearest_nodes, dist_m

MAX_SNAP_M = 300     # drop points that are further than this from any graph node (outside study area)
DEDUPE_M = 150       # same-kind points closer than this are one facility (OSM often has node + polygon)


def _fetch_osm(bbox) -> list[dict]:
    import osmnx as ox
    n, s, e, w = bbox
    tags = {"amenity": ["hospital", "fire_station"]}
    if int(ox.__version__.split(".")[0]) >= 2:
        gdf = ox.features_from_bbox((w, s, e, n), tags)
    else:
        gdf = ox.features_from_bbox(n, s, e, w, tags)
    rows = []
    for idx, r in gdf.iterrows():
        kind = {"hospital": "ambulance", "fire_station": "fire"}.get(r.get("amenity"))
        if kind is None or r.geometry is None:
            continue
        p = r.geometry.representative_point()
        name = r.get("name")
        rows.append({"id": f"osm-{idx[1] if isinstance(idx, tuple) else idx}", "kind": kind,
                     "name": name if isinstance(name, str) else f"{kind} (unnamed)",
                     "lat": p.y, "lon": p.x, "crews": None, "source": "osm"})
    return rows


def _read_fire_csv(path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    rows = []
    with open(p, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not (r.get("lat") and r.get("lon")):
                continue
            rows.append({"id": f"csv-{r['id']}", "kind": "fire", "name": r.get("name", ""),
                         "lat": float(r["lat"]), "lon": float(r["lon"]),
                         "crews": int(r["crews"]) if r.get("crews") else None, "source": "csv"})
    return rows


def _dedupe(rows: list[dict]) -> list[dict]:
    """Keep first of any same-kind pair closer than DEDUPE_M. Pass CSV rows first so they win over OSM."""
    kept = []
    for r in rows:
        if not any(k["kind"] == r["kind"] and dist_m(k["lon"], k["lat"], r["lon"], r["lat"]) < DEDUPE_M
                   for k in kept):
            kept.append(r)
    return kept


def build_assets(G, bbox=config.STUDY_AREA_BBOX, fire_csv=config.FIRE_CSV) -> list[Asset]:
    try:
        osm = _fetch_osm(bbox)
    except Exception as ex:                      # offline / Overpass down: CSV-only still works
        print(f"WARNING: OSM asset fetch failed ({ex}); using CSV only")
        osm = []
    rows = _dedupe(_read_fire_csv(fire_csv) + osm)
    nodes, dists = nearest_nodes(G, [r["lon"] for r in rows], [r["lat"] for r in rows])
    assets, dropped = [], 0
    for r, node, d in zip(rows, nodes, dists):
        if d > MAX_SNAP_M:
            dropped += 1
            continue
        assets.append(Asset(r["id"], r["kind"], node, r["name"],
                            crews=r["crews"] or config.CREWS_DEFAULT[r["kind"]],
                            is_proxy=(r["kind"] == "ambulance")))
    by = {k: sum(a.kind == k for a in assets) for k in ("fire", "ambulance")}
    print(f"assets: {by['fire']} fire stations, {by['ambulance']} hospitals (ambulance proxies); "
          f"{dropped} dropped (>{MAX_SNAP_M} m from graph)")
    return assets


def load_assets(G, use_cache: bool = True, cache_path: str = config.ASSETS_CACHE) -> list[Asset]:
    """Load from the committed JSON cache (offline demo); rebuild from OSM + CSV if missing or stale."""
    p = Path(cache_path)
    if use_cache and p.exists():
        assets = [Asset(**d) for d in json.loads(p.read_text(encoding="utf-8"))]
        if all(a.node in G for a in assets):
            return assets
        print("assets cache does not match this graph; rebuilding")
    assets = build_assets(G)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps([a.__dict__ for a in assets], indent=1), encoding="utf-8")
    return assets