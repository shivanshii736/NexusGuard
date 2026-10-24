"""PERSON 1. Planning-mode baseline: how many zones miss each response target, free-flow vs peak hour.

    python -m nexusguard.network.baseline
Uses P2's compute_coverage(). The engine routes on `travel_time`, so the peak run uses peak_view(G).
Targets come from config.RESPONSE_TARGETS_MIN (read by engine/settings.py).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from nexusguard.network.adapters import peak_view, to_stations, to_wards


def _run(G, wards, stations, services):
    from nexusguard.engine.coverage import compute_coverage, providers_from_stations
    df = compute_coverage(G, wards, providers_from_stations(stations), services=services)
    out = {}
    for svc, g in df.groupby("service", sort=False):
        finite = g.loc[g["eta_s"] != math.inf, "eta_s"]
        worst = g.sort_values("eta_s", ascending=False).head(5)
        out[svc] = {
            "target_min": float(g["target_s"].iloc[0]) / 60, "zones": int(len(g)),
            "covered": int(g["covered"].sum()), "missed": int((~g["covered"]).sum()),
            "avg_pct_nodes_covered": round(float(g["pct_nodes_covered"].mean()), 2),
            "median_eta_min": round(float(finite.median()) / 60, 1) if len(finite) else None,
            "worst_zones": [(r.ward, None if r.eta_s == math.inf else round(r.eta_s / 60, 1))
                            for r in worst.itertuples()],
        }
    return out


def baseline_report(G, assets, zones, members=None, services=("fire", "ambulance")) -> dict:
    wards, stations = to_wards(zones, members), to_stations(assets)
    free, peak = _run(G, wards, stations, services), _run(peak_view(G), wards, stations, services)
    return {svc: {"free_flow": free[svc], "peak": peak[svc]} for svc in free}


def print_report(rep: dict) -> None:
    for svc, r in rep.items():
        f, p = r["free_flow"], r["peak"]
        print(f"\n{svc.upper()}  (target {p['target_min']:.0f} min, {p['zones']} zones)")
        print(f"  free-flow: {f['covered']}/{f['zones']} zones meet target (median ETA {f['median_eta_min']} min)")
        print(f"  peak hour: {p['covered']}/{p['zones']} zones meet target (median ETA {p['median_eta_min']} min)"
              f"  -> {p['missed']} zones MISS it at peak")
        print(f"  avg share of each zone's roads within target at peak: {p['avg_pct_nodes_covered']:.0%}")
        print(f"  worst at peak: {p['worst_zones']}")


if __name__ == "__main__":
    from nexusguard.network.build_graph import load_graph
    from nexusguard.network.assets import load_assets
    from nexusguard.network.zones import load_zones, zone_members
    G = load_graph()
    assets, zones = load_assets(G), load_zones(G)
    rep = baseline_report(G, assets, zones, zone_members(G))
    print_report(rep)
    Path("data/processed").mkdir(parents=True, exist_ok=True)
    Path("data/processed/baseline.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")