"""PERSON 1. Wards -> Zone objects (one representative node each)."""
from nexusguard.types import Zone


def load_zones(G) -> list[Zone]:
    """TODO(P1): load BBMP ward polygons if you can find them (verify availability);
    FALLBACK: regular ~1 km grid cells over the study area. Snap centroid to nearest node."""
    raise NotImplementedError
