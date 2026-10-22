"""PERSON 3. A fire is an incident at a node that needs fire (+ambulance) crews."""
from nexusguard.types import RoadState, Incident


class FireHazard:
    def __init__(self, node: int, severity: int = 2, incident_id: str = "fire-1"):
        self.node, self.severity, self.id = node, severity, incident_id

    def apply(self, G) -> RoadState:
        inc = Incident(self.id, "fire", self.node, self.severity,
                       needs={"fire": 1 + (self.severity > 2), "ambulance": 1})
        return RoadState(incidents=[inc], notes=[f"Fire at node {self.node}"])
