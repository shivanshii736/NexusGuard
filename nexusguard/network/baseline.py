"""PERSON 1. Planning-mode baseline: how many zones miss each response target, using P2's compute_coverage().

    python -m nexusguard.network.baseline
Edge weights / targets come from the engine (engine/routing.py, engine/settings.py), not from here.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from nexusguard.network.adapters import to_stations, to_wards


def baseline_report(G, assets, zones, members=None, services=("fire", "ambulance")) -> dict:
    from nexusguard.engine.coverage import compute_coverage, providers_from_stations
    wards = to_wards(zones, members)
    df = compute_coverage(G, wards, providers_from_stations(to_stations(assets)), services=services)
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


def print_report(rep: dict) -> None:
    for svc, r in rep.items():
        print(f"\n{svc.upper()}  (target {r['target_min']:.0f} min, {r['zones']} zones)")
        print(f"  {r['covered']}/{r['zones']} zones meet target  -> {r['missed']} zones MISS it")
        print(f"  avg share of each zone's roads within target: {r['avg_pct_nodes_covered']:.0%}; "
              f"median ETA {r['median_eta_min']} min")
        print(f"  worst: {r['worst_zones']}")


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