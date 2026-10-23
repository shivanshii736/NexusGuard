"""Engine tunables. Reads nexusguard.config when it defines them, else safe defaults.

Expected (optional) names in nexusguard/config.py:
    RESPONSE_TARGETS_MIN = {"ambulance": 8, "fire": 8, "rescue": 15}
"""
from __future__ import annotations

DEFAULT_TARGETS_MIN = {"ambulance": 8.0, "fire": 8.0, "rescue": 15.0}

# Time a crew stays committed on scene (seconds), on top of travel there and back.
ON_SCENE_S = {"ambulance": 30 * 60, "fire": 60 * 60, "rescue": 90 * 60}

FALLBACK_SPEED_MPS = 30 / 3.6   # used only if an edge has neither travel_time nor speed


def get_targets_s() -> dict:
    """Response-time targets in SECONDS per service."""
    mins = dict(DEFAULT_TARGETS_MIN)
    try:
        from nexusguard import config  # type: ignore
        mins.update(getattr(config, "RESPONSE_TARGETS_MIN", {}) or {})
    except Exception:
        pass
    return {k: float(v) * 60.0 for k, v in mins.items()}
