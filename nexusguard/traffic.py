"""Time-of-day speed multipliers. ALL VALUES ARE ASSUMPTIONS, not measured traffic (slide 8/9)."""
from __future__ import annotations

PEAK_HOURS = frozenset({8, 9, 10, 17, 18, 19, 20})
SHOULDER_HOURS = frozenset({7, 11, 16, 21})
DEFAULT_PEAK_HOUR = 18


def congestion_factor(hour: int) -> float:
    """Travel-time multiplier on arterials at this hour of day (0-23)."""
    h = int(hour) % 24
    return 1.30 if h in PEAK_HOURS else 1.15 if h in SHOULDER_HOURS else 1.0


def time_multiplier(hour: int, road_class: str) -> float:
    """Arterials take the full congestion factor, local roads half of it."""
    f = congestion_factor(hour)
    return f if road_class == "arterial" else 1 + (f - 1) * 0.5
