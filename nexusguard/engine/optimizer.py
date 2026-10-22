"""PERSON 2. Where to pre-position vehicles."""
from nexusguard.types import Asset, Zone, RoadState, Intervention


def recommend_prepositioning(G, assets: list[Asset], zones: list[Zone], state: RoadState,
                             kind: str, k: int, candidate_nodes: list[int]) -> Intervention:
    """TODO(P2): greedy max-coverage. Repeat k times: add a temporary Asset at each candidate node,
    re-run coverage(), keep the node with the biggest gain in covered zones (or population).
    Return Intervention(before, after). Restrict candidates (~200 nodes) to stay fast."""
    raise NotImplementedError
