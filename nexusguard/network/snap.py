"""PERSON 1. Snap lon/lat points to the nearest graph node (pure numpy: no scikit-learn / osmnx needed)."""
import math
import numpy as np


def node_arrays(G):
    ids = np.array(list(G.nodes), dtype=np.int64)
    xs = np.array([G.nodes[n]["x"] for n in ids], dtype=float)
    ys = np.array([G.nodes[n]["y"] for n in ids], dtype=float)
    return ids, xs, ys


def nearest_nodes(G, lons, lats):
    """Return (node_ids, distance_m) lists, one entry per input point."""
    ids, xs, ys = node_arrays(G)
    out, dist = [], []
    for lo, la in zip(lons, lats):
        kx = 111320.0 * math.cos(math.radians(la))
        d = np.hypot((xs - lo) * kx, (ys - la) * 110540.0)
        i = int(d.argmin())
        out.append(int(ids[i]))
        dist.append(float(d[i]))
    return out, dist


def dist_m(lon1, lat1, lon2, lat2) -> float:
    kx = 111320.0 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot((lon1 - lon2) * kx, (lat1 - lat2) * 110540.0)