"""PERSON 1. Wards -> Zone objects (one representative node each). Ward polygons if present, else ~1 km grid."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from nexusguard import config
from nexusguard.types import Zone
from nexusguard.network.snap import node_arrays

MIN_NODES = 3   # skip cells/wards with (almost) no roads: lakes, parks, edge slivers


def _grid_cells(G, cell_m: float):
    """[(Zone, [member node ids])] for a regular grid over the graph's extent."""
    ids, xs, ys = node_arrays(G)
    lat0, lon0 = ys.min(), xs.min()
    dlat = cell_m / 110540.0
    dlon = cell_m / (111320.0 * math.cos(math.radians((ys.min() + ys.max()) / 2)))
    r = ((ys - lat0) // dlat).astype(int)
    c = ((xs - lon0) // dlon).astype(int)
    cells = []
    for rr, cc in sorted(set(zip(r.tolist(), c.tolist()))):
        idx = np.where((r == rr) & (c == cc))[0]
        if len(idx) < MIN_NODES:
            continue
        cy, cx = lat0 + (rr + 0.5) * dlat, lon0 + (cc + 0.5) * dlon
        d = np.hypot((xs[idx] - cx) * 111320.0 * math.cos(math.radians(cy)), (ys[idx] - cy) * 110540.0)
        cells.append((Zone(f"g{rr}_{cc}", f"Grid {rr},{cc}", int(ids[idx[int(d.argmin())]])),
                      [int(n) for n in ids[idx]]))
    return cells


def grid_zones(G, cell_m: float = config.GRID_CELL_M) -> list[Zone]:
    """Each non-empty grid cell -> a Zone at the node closest to the cell centre."""
    return [z for z, _ in _grid_cells(G, cell_m)]


def _col(row, names):
    for n in names:
        if n in row and row[n] is not None and str(row[n]) not in ("", "nan", "None"):
            return row[n]
    return None


def _ward_cells(G, path: str):
    """[(Zone, [member node ids])] from ward polygons. Representative node = node inside nearest the centre."""
    import geopandas as gpd
    gdf = gpd.read_file(path).to_crs(4326)
    ids, xs, ys = node_arrays(G)
    pts = gpd.GeoSeries(gpd.points_from_xy(xs, ys), crs=4326)
    cells = []
    for i, (_, row) in enumerate(gdf.iterrows()):
        inside = np.where(pts.within(row.geometry).to_numpy())[0]
        if len(inside) < MIN_NODES:
            continue
        c = row.geometry.representative_point()
        d = np.hypot((xs[inside] - c.x) * 111320.0 * math.cos(math.radians(c.y)), (ys[inside] - c.y) * 110540.0)
        no = _col(row, ["ward_no", "WARD_NO", "KGISWardNo", "Ward_No", "id"])
        name = _col(row, ["ward_name", "WARD_NAME", "KGISWardName", "Ward_Name", "name", "Name"])
        pop = _col(row, ["population", "POPULATION", "Population", "pop", "POP_TOTAL"])
        cells.append((Zone(f"w{no if no is not None else i}", str(name or f"Ward {no or i}"),
                           int(ids[inside[int(d.argmin())]]), float(pop) if pop is not None else None),
                      [int(n) for n in ids[inside]]))
    return cells


def ward_zones(G, path: str = config.WARDS_FILE) -> list[Zone]:
    return [z for z, _ in _ward_cells(G, path)]


def zone_members(G) -> dict:
    """zone_id -> tuple of all graph nodes inside that zone (same mode the cached zones were built in)."""
    cells = _ward_cells(G, config.WARDS_FILE) if Path(config.WARDS_FILE).exists() \
        else _grid_cells(G, config.GRID_CELL_M)
    return {z.id: tuple(nodes) for z, nodes in cells}


def load_zones(G, use_cache: bool = True, cache_path: str = config.ZONES_CACHE) -> list[Zone]:
    p = Path(cache_path)
    if use_cache and p.exists():
        zones = [Zone(**d) for d in json.loads(p.read_text(encoding="utf-8"))]
        if zones and all(z.node in G for z in zones):
            return zones
        print("zones cache does not match this graph; rebuilding")
    if Path(config.WARDS_FILE).exists():
        zones = ward_zones(G)
        print(f"zones: {len(zones)} wards from {config.WARDS_FILE}")
    else:
        zones = grid_zones(G)
        print(f"zones: {len(zones)} grid cells (~{config.GRID_CELL_M} m), no ward file at {config.WARDS_FILE}")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps([z.__dict__ for z in zones], indent=1), encoding="utf-8")
    return zones