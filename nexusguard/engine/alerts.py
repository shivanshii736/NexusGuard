"""Rule-based, threshold alerts: fire only when response DEGRADES (no change -> no alert)."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd

from .coverage import coverage_summary
from .dispatch import DispatchResult
from .settings import get_targets_s

CRITICAL, WARNING = "critical", "warning"


@dataclass(frozen=True)
class Alert:
    level: str
    code: str            # WARD_UNCOVERED | WARD_UNREACHABLE | WARD_ETA_DEGRADED | COVERAGE_DROP |
                         # INCIDENT_UNSERVED | INCIDENT_LATE | CONTENTION_DELAY
    message: str
    subject: str         # ward or incident id
    service: str
    value: float = 0.0
    threshold: float = 0.0


def _mins(s: float) -> str:
    return "unreachable" if s == math.inf else f"{s / 60:.1f} min"


class AlertEngine:
    """Compares current state with a baseline and emits only NEW alerts (deduped by key)."""

    def __init__(self, targets_s: Optional[Dict[str, float]] = None,
                 eta_degrade_pct: float = 25.0, eta_degrade_min_s: float = 60.0,
                 coverage_drop_pp: float = 5.0, contention_delay_s: float = 120.0):
        self.targets_s = targets_s or get_targets_s()
        self.eta_degrade_pct = eta_degrade_pct
        self.eta_degrade_min_s = eta_degrade_min_s
        self.coverage_drop_pp = coverage_drop_pp
        self.contention_delay_s = contention_delay_s
        self._active: Set[Tuple[str, str, str]] = set()

    def reset(self) -> None:
        self._active.clear()

    @property
    def active_keys(self):
        return set(self._active)

    def evaluate(self, baseline: pd.DataFrame, current: pd.DataFrame,
                 dispatch: Optional[DispatchResult] = None) -> List[Alert]:
        found: List[Alert] = []
        base = baseline.set_index(["ward_id", "service"])
        for _, r in current.iterrows():
            b = base.loc[(r["ward_id"], r["service"])]
            svc, ward = r["service"], r["ward"]
            if r["eta_s"] == math.inf and b["eta_s"] < math.inf:
                found.append(Alert(CRITICAL, "WARD_UNREACHABLE",
                                   f"{ward} is cut off from {svc} response", r["ward_id"], svc,
                                   math.inf, r["target_s"]))
            elif b["covered"] and not r["covered"]:
                found.append(Alert(CRITICAL, "WARD_UNCOVERED",
                                   f"{ward}: {svc} ETA {_mins(b['eta_s'])} -> {_mins(r['eta_s'])} "
                                   f"(target {_mins(r['target_s'])})", r["ward_id"], svc,
                                   r["eta_s"], r["target_s"]))
            elif (r["eta_s"] < math.inf and b["eta_s"] < math.inf
                  and r["eta_s"] - b["eta_s"] >= self.eta_degrade_min_s
                  and r["eta_s"] > b["eta_s"] * (1 + self.eta_degrade_pct / 100)):
                found.append(Alert(WARNING, "WARD_ETA_DEGRADED",
                                   f"{ward}: {svc} ETA slower by {_mins(r['eta_s'] - b['eta_s'])}",
                                   r["ward_id"], svc, r["eta_s"], b["eta_s"]))

        sb, sc = coverage_summary(baseline).set_index("service"), coverage_summary(current).set_index("service")
        for svc in sc.index:
            drop = sb.loc[svc, "pct_wards_covered"] - sc.loc[svc, "pct_wards_covered"]
            if drop >= self.coverage_drop_pp:
                found.append(Alert(WARNING, "COVERAGE_DROP",
                                   f"{svc} coverage fell {drop:.0f} pp to {sc.loc[svc, 'pct_wards_covered']:.0f}% of wards",
                                   "city", svc, sc.loc[svc, "pct_wards_covered"], self.coverage_drop_pp))

        if dispatch is not None:
            for inc_id, svc in dispatch.unmet:
                found.append(Alert(CRITICAL, "INCIDENT_UNSERVED",
                                   f"Incident {inc_id}: no {svc} crew available or reachable", inc_id, svc))
            for a in dispatch.assignments:
                tgt = self.targets_s.get(a.service, math.inf)
                if a.eta_s > tgt:
                    found.append(Alert(WARNING, "INCIDENT_LATE",
                                       f"Incident {a.incident_id}: {a.service} ETA {_mins(a.eta_s)} exceeds target {_mins(tgt)}",
                                       a.incident_id, a.service, a.eta_s, tgt))
                if a.delay_s >= self.contention_delay_s:
                    found.append(Alert(WARNING, "CONTENTION_DELAY",
                                       f"Incident {a.incident_id}: {a.service} delayed {_mins(a.delay_s)} by competing incidents",
                                       a.incident_id, a.service, a.delay_s, self.contention_delay_s))

        new = []
        keys_now = set()
        for al in found:
            key = (al.code, al.subject, al.service)
            keys_now.add(key)
            if key not in self._active:
                new.append(al)
        self._active = keys_now          # cleared alerts can re-fire if the problem returns
        return sorted(new, key=lambda a: (a.level != CRITICAL, a.code, a.subject, a.service))
