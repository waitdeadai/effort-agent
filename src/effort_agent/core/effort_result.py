"""EffortResult — the structured output of effort evaluation."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from effort_agent.core.verdict import EffortVerdict


@dataclass
class EffortResult:
    """
    The result of an effort evaluation on a task.

    Attributes:
        verdict: The overall process integrity verdict (DONE/REDO/FAIL).
        reasoning: Human-readable explanation of why this verdict was reached.
        issues: List of specific issues detected (e.g., "single_pass",
                "skipped_verification", "good_enough_language").
        task_hash: SHA-256 hash of the task description (for deduplication).
        task_description: The original task description.
        file_path: Primary file path this task operated on (if applicable).
        effort_level: The effort level used for evaluation.
        verification_evidence_found: Whether any verification evidence was detected.
        draft_count: Number of draft/iteration cycles detected.
        shortcut_phrases_found: List of shortcut phrases detected in the output.
        timestamp: ISO-8601 timestamp of when evaluation occurred.
        retry_count: Number of times this task has been redone.
        principle_violated: The core principle that was violated (if any).
        category: Issue category — "process", "verification", "shortcut", "research".
        was_applied: Whether the REDO was actually applied by the agent.
    """

    verdict: EffortVerdict
    reasoning: str
    issues: list[str] = field(default_factory=list)
    task_hash: Optional[str] = None
    task_description: Optional[str] = None
    file_path: Optional[str] = None
    effort_level: str = "thorough"
    verification_evidence_found: bool = False
    draft_count: int = 0
    shortcut_phrases_found: list[str] = field(default_factory=list)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    retry_count: int = 0
    principle_violated: Optional[str] = None
    category: str = "process"
    was_applied: bool = False

    def to_dict(self) -> dict:
        """Serialize to a dictionary suitable for JSON/JSONL."""
        return {
            "verdict": self.verdict.value if isinstance(self.verdict, EffortVerdict) else self.verdict,
            "reasoning": self.reasoning,
            "issues": self.issues,
            "task_hash": self.task_hash,
            "task_description": self.task_description,
            "file_path": self.file_path,
            "effort_level": self.effort_level,
            "verification_evidence_found": self.verification_evidence_found,
            "draft_count": self.draft_count,
            "shortcut_phrases_found": self.shortcut_phrases_found,
            "timestamp": self.timestamp,
            "retry_count": self.retry_count,
            "principle_violated": self.principle_violated,
            "category": self.category,
            "was_applied": self.was_applied,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EffortResult":
        """Deserialize from a dictionary."""
        from effort_agent.core.verdict import EffortVerdict

        if isinstance(data.get("verdict"), str):
            data["verdict"] = EffortVerdict(data["verdict"])
        return cls(**data)

    def is_retry_allowed(self) -> bool:
        """Returns True if this verdict can be retried."""
        return self.verdict == EffortVerdict.REDO

    def is_hard_fail(self) -> bool:
        """Returns True if this verdict is a hard failure (no retry)."""
        return self.verdict == EffortVerdict.FAIL
