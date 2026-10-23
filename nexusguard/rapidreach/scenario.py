"""Scenario replay: a timeline of hazard events, scrubbed by minute.

JSON format (see scenarios/compound.json):
  {"name": "...", "description": "...", "duration_min": 90,
   "events": [{"t_min": 0, "label": "...", "end_min": null, "hazard": {"type": "flood", ...}}]}

`ScenarioPlayer.state_at(t)` returns the hazards active at minute t, so the same scenario can
be stepped by a slider, auto-played, or fed to a backtest later.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import json
from pathlib import Path
import networkx as nx

from .hazards import Hazard, HazardEffect, hazard_from_dict, merge_effects


@dataclass
class ScenarioEvent:
    t_min: float
    hazard: Hazard
    label: str = ""
    end_min: float | None = None

    def active_at(self, t: float) -> bool:
        return self.t_min <= t and (self.end_min is None or t < self.end_min)


@dataclass
class Scenario:
    name: str
    description: str = ""
    duration_min: float = 60
    events: list[ScenarioEvent] = field(default_factory=list)
    # where the events come from; a backtest scenario must cite its sourced incident reports here
    source: str = "synthetic demo scenario (not a real incident)"

    def event_times(self) -> list[float]:
        return sorted({e.t_min for e in self.events})

    @classmethod
    def from_dict(cls, d: dict) -> "Scenario":
        evs = [ScenarioEvent(e["t_min"], hazard_from_dict(e["hazard"]), e.get("label", ""), e.get("end_min"))
               for e in d["events"]]
        return cls(d["name"], d.get("description", ""), d.get("duration_min", 60), sorted(evs, key=lambda e: e.t_min),
                   d.get("source", cls.source))

    @classmethod
    def load(cls, path: str | Path) -> "Scenario":
        return cls.from_dict(json.loads(Path(path).read_text()))

    def to_dict(self) -> dict:
        return {"name": self.name, "description": self.description, "duration_min": self.duration_min,
                "source": self.source,
                "events": [{"t_min": e.t_min, "end_min": e.end_min, "label": e.label, "hazard": e.hazard.to_dict()}
                           for e in self.events]}


class ScenarioPlayer:
    def __init__(self, scenario: Scenario, G: nx.Graph):
        self.scenario, self.G = scenario, G

    def active_events(self, t: float) -> list[ScenarioEvent]:
        return [e for e in self.scenario.events if e.active_at(t)]

    def effect_at(self, t: float) -> HazardEffect:
        effs = []
        for e in self.active_events(t):
            eff = e.hazard.apply(self.G)
            for inc in eff.incidents:
                inc.t_start_min = e.t_min
            effs.append(eff)
        return merge_effects(effs)

    def timeline(self) -> list[tuple[float, str]]:
        return [(e.t_min, e.label or e.hazard.describe()) for e in self.scenario.events]


def load_scenarios(folder: str | Path) -> dict[str, Scenario]:
    out = {}
    for p in sorted(Path(folder).glob("*.json")):
        s = Scenario.load(p)
        out[s.name] = s
    return out
