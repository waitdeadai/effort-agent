"""Effort Verdict — process integrity evaluation outcomes."""

from enum import Enum


class EffortVerdict(str, Enum):
    """
    Verdict returned by EffortAgent after evaluating a task's execution.

    Attributes:
        DONE: Work meets effort standards. Shortcuts were avoided,
               verification was performed, and iteration requirements were met.
        REDO: Shortcuts detected. Work must be redone with more rigor.
               This is a soft rejection — the agent should try again.
        FAIL: Catastrophic failure. Work is so far below standards that
              execution should halt. Reserved for complete abandonment
              of process (e.g., no effort.md found when required,
              all verification skipped, etc.).
    """

    DONE = "done"
    """Work meets effort standards — proceed."""

    REDO = "redo"
    """Shortcuts detected — bounce back for revision."""

    FAIL = "fail"
    """Catastrophic failure — halt execution."""


# Human-readable descriptions for each verdict
VERDICT_DESCRIPTIONS = {
    EffortVerdict.DONE: "Work meets effort standards. All required verification completed, "
    "iteration requirements satisfied, and no shortcuts detected.",
    EffortVerdict.REDO: "Shortcuts or deficiencies detected. "
    "Work must be redone with greater rigor before proceeding.",
    EffortVerdict.FAIL: "Catastrophic process failure. "
    "Execution cannot continue until fundamental process issues are resolved.",
}
