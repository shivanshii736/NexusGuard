"""PERSON 2. Threshold alerts. Rule-based, only when response DEGRADES."""
from nexusguard.types import CoverageReport, Assignment, Alert


def make_alerts(baseline: CoverageReport, current: CoverageReport,
                assignments: list[Assignment]) -> list[Alert]:
    """TODO(P2): critical = incident breach or unassigned; warn = zone newly beyond target
    (covered in baseline, not now); info = coverage drop > X points. No alert if nothing worsened."""
    raise NotImplementedError
