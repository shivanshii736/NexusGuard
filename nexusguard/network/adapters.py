"""PERSON 1. Convert P1's Asset/Zone (types.py) into P2's engine models (engine/models.py).

Keeps both contracts untouched: P1 loaders keep returning Asset/Zone; the engine gets Station/Ward.
"""
from __future__ import annotations

from nexusguard.engine.models import Station, Ward


def to_stations(assets) -> list:
    """Asset(crews) -> Station(units). Same kind strings ('ambulance' | 'fire' | 'rescue')."""
    return [Station(id=a.id, name=a.name or a.id, kind=a.kind, node=a.node, units=a.crews) for a in assets]


def to_wards(zones, members: dict | None = None) -> list:
    """Zone -> Ward. `members` (zones.zone_members(G)) fills Ward.nodes so the engine can report
    pct_nodes_covered. Population falls back to 1.0 (unweighted) when unknown, e.g. grid cells."""
    members = members or {}
    return [Ward(id=z.id, name=z.name, centroid=z.node, nodes=tuple(members.get(z.id, ())),
                 population=z.population if z.population is not None else 1.0) for z in zones]