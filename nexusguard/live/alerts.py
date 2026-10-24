"""Rule-based threshold alerts, fired only on DEGRADATION (slide 10: "NO -> continue monitoring; no alert").

Rules:
  * breach  - a required unit's ETA exceeds its target, or no free/reachable unit exists
  * ward    - a ward's coverage for a service is below `ward_threshold` AND has dropped at least
              `min_drop` below the no-hazard baseline (so persistent planning gaps are NOT live alerts).
              One alert per service, listing every affected ward, so a compound event stays readable.
Planning-mode gaps (below threshold even at baseline) come from `persistent_gaps`.
"""
from __future__ import annotations
from dataclasses import dataclass

from .response_stub import Assignment


@dataclass(frozen=True)
class AlertRules:
    ward_threshold: float = 0.80
    min_drop: float = 0.10


@dataclass(frozen=True)
class Alert:
    key: str
    level: str        # "error" (no unit) | "warning"
    kind: str         # "breach" | "ward"
    message: str
    wards: tuple[str, ...] = ()     # for "ward" alerts: the affected wards


def compute_alerts(assignments: list[Assignment], cov: dict, cov0: dict, rules: AlertRules = AlertRules()) -> list[Alert]:
    out: list[Alert] = []
    groups: dict[tuple[str, str], list[Assignment]] = {}
    for a in assignments:
        groups.setdefault((a.incident_id, a.service), []).append(a)
    for (inc, svc), items in sorted(groups.items()):
        missing = [a for a in items if a.asset_id is None]
        late = [a for a in items if a.asset_id is not None and a.breach]
        if not missing and not late:
            continue
        key = f"breach|{inc}|{svc}"
        if missing:
            msg = f"{inc}: no free or reachable {svc} unit ({len(missing)} of {len(items)} needed)"
            if late:
                msg += f"; the other{'s' if len(late) > 1 else ''} arrive late (worst {max(a.eta_s for a in late) / 60:.1f} min)"
            out.append(Alert(key, "error", "breach", msg))
        else:
            w = max(late, key=lambda a: a.eta_s)
            out.append(Alert(key, "warning", "breach",
                             f"{inc}: {svc} {w.asset_id} ETA {w.eta_s / 60:.1f} min exceeds {w.target_s / 60:.0f} min target"
                             + (f" ({len(late)} of {len(items)} units late)" if len(items) > 1 else "")))
    services = sorted({svc for w in cov for svc in cov[w]})
    for svc in services:
        hit = [w for w in sorted(cov) if cov[w][svc] < rules.ward_threshold
               and (cov0[w][svc] - cov[w][svc]) >= rules.min_drop - 1e-9]
        if hit:
            worst = min(hit, key=lambda w: cov[w][svc])
            out.append(Alert(f"ward|{svc}|{','.join(hit)}", "warning", "ward",
                             f"{svc.title()} coverage degraded in {len(hit)} ward{'s' if len(hit) > 1 else ''} "
                             f"({', '.join(hit)}); worst {worst} at {cov[worst][svc]:.0%} "
                             f"(baseline {cov0[worst][svc]:.0%})", tuple(hit)))
    return out


def persistent_gaps(cov0: dict, rules: AlertRules = AlertRules()) -> list[tuple[str, str, float]]:
    """Planning mode: ward/service pairs below the threshold even with no hazard."""
    return [(w, s, v) for w in sorted(cov0) for s, v in sorted(cov0[w].items()) if v < rules.ward_threshold]


def new_alerts(now: list[Alert], previous: list[Alert] | None) -> set[str]:
    """Keys present now but not at the previous step (all of them if there is no previous step)."""
    prev = {a.key for a in previous} if previous is not None else set()
    return {a.key for a in now} - prev
