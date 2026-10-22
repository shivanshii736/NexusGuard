"""PERSON 3. Manual incident drop: collapse, lake breach, anything else."""
from nexusguard.types import RoadState, Incident


class GenericIncident:
    def __init__(self, kind: str, node: int, needs: dict, severity: int = 2,
                 closed_edges: set | None = None, incident_id: str | None = None):
        self.inc = Incident(incident_id or f"{kind}-{node}", kind, node, severity, needs)
        self.closed = closed_edges or set()

    def apply(self, G) -> RoadState:
        return RoadState(closed_edges=set(self.closed), incidents=[self.inc],
                         notes=[f"{self.inc.kind} at node {self.inc.node}"])
