"""PERSON 3. Every hazard turns an event into a RoadState. That is the whole contract."""
from typing import Protocol
from nexusguard.types import RoadState


class Hazard(Protocol):
    def apply(self, G) -> RoadState: ...
