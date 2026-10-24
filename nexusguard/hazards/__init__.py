from .base import Hazard, HazardEffect, Incident, merge_effects
from .flood import FloodHazard
from .fire import FireHazard
from .generic import GenericIncident, GENERIC_PRESETS

HAZARD_TYPES: dict[str, type[Hazard]] = {
    FloodHazard.type_name: FloodHazard,
    FireHazard.type_name: FireHazard,
    GenericIncident.type_name: GenericIncident,
}


def hazard_from_dict(d: dict) -> Hazard:
    d = dict(d)
    kind = d.pop("type")
    return HAZARD_TYPES[kind](**d)


__all__ = ["Hazard", "HazardEffect", "Incident", "merge_effects", "FloodHazard", "FireHazard",
           "GenericIncident", "GENERIC_PRESETS", "HAZARD_TYPES", "hazard_from_dict"]
