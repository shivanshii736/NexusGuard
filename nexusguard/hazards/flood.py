"""PERSON 3. Rainfall + terrain -> closed/slowed road edges."""
from nexusguard.types import RoadState


class FloodHazard:
    def __init__(self, rainfall_mm_per_hr: float, hotspot_nodes: list[int] | None = None):
        self.rain = rainfall_mm_per_hr
        self.hotspots = hotspot_nodes or []

    def apply(self, G) -> RoadState:
        """TODO(P3): simple, explainable rule: edges near low-lying nodes / lake-adjacent /
        known hotspot underpasses close above a rain threshold, slow down below it.
        Document every threshold as ASSUMED. Keep deterministic."""
        raise NotImplementedError
