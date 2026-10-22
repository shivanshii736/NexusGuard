"""PERSON 2 (planning mode uses it too). Ward-level coverage for one kind of responder."""
import math
from nexusguard import config
from nexusguard.types import Asset, Zone, RoadState, CoverageReport
from nexusguard.engine.routing import effective_graph, nearest_asset_eta


def coverage(G, assets: list[Asset], zones: list[Zone], state: RoadState,
             kind: str, target_s: float | None = None) -> CoverageReport:
    target = target_s or config.TARGETS_S[kind]
    H = effective_graph(G, state)
    sources = [a.node for a in assets if a.kind == kind and a.crews > 0]
    eta = nearest_asset_eta(H, sources)
    eta_by_zone = {z.id: eta.get(z.node, math.inf) for z in zones}
    covered = {zid for zid, t in eta_by_zone.items() if t <= target}
    pops = [z.population for z in zones]
    pct_pop = None
    if all(p is not None for p in pops) and sum(pops) > 0:
        pct_pop = sum(z.population for z in zones if z.id in covered) / sum(pops)
    return CoverageReport(kind, target, eta_by_zone, covered, len(covered) / max(len(zones), 1), pct_pop)
