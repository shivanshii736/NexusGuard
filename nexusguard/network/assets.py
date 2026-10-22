"""PERSON 1. Response assets: hospitals (ambulance proxies), fire stations, rescue."""
from nexusguard.types import Asset


def load_assets(G) -> list[Asset]:
    """TODO(P1): query OSM amenity=hospital / amenity=fire_station inside the study area,
    snap each to nearest node (osmnx.nearest_nodes). Hospitals => kind='ambulance', is_proxy=True.
    Keep a hand-checked fire_stations.csv as fallback (OSM can be incomplete)."""
    raise NotImplementedError
