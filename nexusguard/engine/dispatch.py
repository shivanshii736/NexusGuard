"""PERSON 2. Resource contention: limited crews, simultaneous incidents."""
from nexusguard.types import Asset, RoadState, Assignment


def dispatch(G, assets: list[Asset], state: RoadState) -> tuple[list[Assignment], list[Asset]]:
    """TODO(P2): deterministic greedy. Sort incidents by (-severity, t_start). For each need
    (kind, n crews): pick nearest FREE asset by ETA on effective_graph, decrement its crews,
    record Assignment (breach if eta > TARGETS_S[kind] or unassigned).
    Return (assignments, assets_with_remaining_crews) so coverage() can be re-run on what is left.
    Deterministic => reproducible demo."""
    raise NotImplementedError
