"""EffortMemory — append-only JSONL store for effort evaluation history."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Iterator

from effort_agent.core.verdict import EffortVerdict


class MemoryEntry:
    """
    A single memory entry with slots for efficient storage.

    Attributes:
        entry_id: Unique entry identifier.
        timestamp: ISO-8601 timestamp.
        task_hash: SHA-256 hash of task description.
        task_description: Original task description.
        file_path: Primary file path.
        verdict: Verdict (done/redo/fail).
        reasoning: Human-readable explanation.
        issues: List of issues detected.
        principle_violated: The principle that was violated.
        category: Issue category.
        was_applied: Whether REDO was applied.
        applied_correctly: Whether applying the REDO fixed the issue.
        retry_count: How many times this task was retried.
        why_this_matters: Mentor-mode explanation.
        severity: Severity level (P0/P1/P2/P3).
    """

    __slots__ = (
        "entry_id",
        "timestamp",
        "task_hash",
        "task_description",
        "file_path",
        "verdict",
        "reasoning",
        "issues",
        "principle_violated",
        "category",
        "was_applied",
        "applied_correctly",
        "retry_count",
        "why_this_matters",
        "severity",
    )

    def __init__(
        self,
        entry_id: str,
        timestamp: str,
        task_hash: str,
        task_description: str,
        file_path: Optional[str],
        verdict: str,
        reasoning: str,
        issues: list[str],
        principle_violated: Optional[str] = None,
        category: str = "process",
        was_applied: bool = False,
        applied_correctly: Optional[bool] = None,
        retry_count: int = 0,
        why_this_matters: str = "",
        severity: str = "P2",
    ):
        self.entry_id = entry_id
        self.timestamp = timestamp
        self.task_hash = task_hash
        self.task_description = task_description
        self.file_path = file_path
        self.verdict = verdict
        self.reasoning = reasoning
        self.issues = issues
        self.principle_violated = principle_violated
        self.category = category
        self.was_applied = was_applied
        self.applied_correctly = applied_correctly
        self.retry_count = retry_count
        self.why_this_matters = why_this_matters
        self.severity = severity

    def to_dict(self) -> dict:
        """Serialize to dict for JSONL storage."""
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "task_hash": self.task_hash,
            "task_description": self.task_description,
            "file_path": self.file_path,
            "verdict": self.verdict,
            "reasoning": self.reasoning,
            "issues": self.issues,
            "principle_violated": self.principle_violated,
            "category": self.category,
            "was_applied": self.was_applied,
            "applied_correctly": self.applied_correctly,
            "retry_count": self.retry_count,
            "why_this_matters": self.why_this_matters,
            "severity": self.severity,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryEntry":
        """Deserialize from dict."""
        return cls(
            entry_id=data.get("entry_id", ""),
            timestamp=data.get("timestamp", ""),
            task_hash=data.get("task_hash", ""),
            task_description=data.get("task_description", ""),
            file_path=data.get("file_path"),
            verdict=data.get("verdict", "done"),
            reasoning=data.get("reasoning", ""),
            issues=data.get("issues", []),
            principle_violated=data.get("principle_violated"),
            category=data.get("category", "process"),
            was_applied=data.get("was_applied", False),
            applied_correctly=data.get("applied_correctly"),
            retry_count=data.get("retry_count", 0),
            why_this_matters=data.get("why_this_matters", ""),
            severity=data.get("severity", "P2"),
        )

    def __repr__(self) -> str:
        return (
            f"MemoryEntry({self.verdict} | {self.task_description[:30]}... | "
            f"applied={self.was_applied})"
        )


class EffortMemory:
    """
    Append-only JSONL store for effort evaluation entries.

    Tracks all effort verdicts across tasks for analysis, auditing,
    and consolidation into semantic memory.

    Consolidation triggers (any one triggers):
    - 20+ entries accumulated
    - 24 hours elapsed since last consolidation
    - Manual trigger via consolidate()

    Format (JSONL):
        {"entry_id": "em-a1b2c3d4", "timestamp": "2026-04-13T10:30:00Z",
         "task_hash": "sha256...", "task_description": "Build user auth module",
         "file_path": "auth.py", "verdict": "REDO",
         "reasoning": "Single-pass completion detected",
         "issues": ["single_pass"], "principle": "Always verify before claiming done",
         "category": "process", "was_applied": false}
    """

    FORMAT_VERSION = "1.0"

    def __init__(self, path: str | Path | None = None):
        """
        Initialize EffortMemory.

        Args:
            path: Path to the JSONL file. If None, uses "effort.memory"
                  in the current working directory.
        """
        self.path = Path(path) if path else Path("effort.memory")
        self._entry_count: Optional[int] = None
        self._last_consolidation: Optional[datetime] = None
        self._consolidation_threshold = 20
        self._consolidation_interval = timedelta(hours=24)

    # -------------------------------------------------------------------------
    # Writing
    # -------------------------------------------------------------------------

    def append(
        self,
        task_description: str,
        verdict: EffortVerdict,
        reasoning: str,
        issues: list[str],
        principle_violated: Optional[str] = None,
        category: str = "process",
        file_path: Optional[str] = None,
        was_applied: bool = False,
        retry_count: int = 0,
    ) -> str:
        """
        Append a new entry to the memory store.

        Args:
            task_description: The task that was evaluated.
            verdict: The verdict returned.
            reasoning: Human-readable explanation.
            issues: List of issues detected.
            principle_violated: The principle that was violated.
            category: Issue category.
            file_path: Primary file path operated on.
            was_applied: Whether the REDO was applied by the agent.
            retry_count: How many times this task has been retried.

        Returns:
            The entry_id of the appended entry.
        """
        entry_id = f"em-{uuid.uuid4().hex[:8]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        task_hash = self._hash_task(task_description)

        entry = {
            "entry_id": entry_id,
            "format_version": self.FORMAT_VERSION,
            "timestamp": timestamp,
            "task_hash": task_hash,
            "task_description": task_description,
            "file_path": file_path,
            "verdict": verdict.value if isinstance(verdict, EffortVerdict) else verdict,
            "reasoning": reasoning,
            "issues": issues,
            "principle": principle_violated,
            "category": category,
            "was_applied": was_applied,
            "retry_count": retry_count,
        }

        self._write_entry(entry)
        self._entry_count = None  # invalidate cache
        return entry_id

    def _write_entry(self, entry: dict) -> None:
        """Write a single entry to the JSONL file (append mode)."""
        line = json.dumps(entry, ensure_ascii=False)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    # -------------------------------------------------------------------------
    # Reading
    # -------------------------------------------------------------------------

    def entries(
        self,
        verdict_filter: Optional[EffortVerdict] = None,
        category_filter: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Iterator[dict]:
        """
        Iterate over entries in the memory store.

        Args:
            verdict_filter: If set, only return entries with this verdict.
            category_filter: If set, only return entries with this category.
            limit: Maximum number of entries to return (most recent first).

        Yields:
            Dictionaries representing each entry.
        """
        if not self.path.exists():
            return

        # Read file in reverse to get most recent entries first
        lines = self._read_lines_reversed()
        count = 0

        for line in lines:
            try:
                entry = json.loads(line.strip())
            except json.JSONDecodeError:
                continue

            if verdict_filter:
                ev = entry.get("verdict")
                if (isinstance(ev, str) and ev != verdict_filter.value) or ev != verdict_filter:
                    continue

            if category_filter:
                if entry.get("category") != category_filter:
                    continue

            yield entry
            count += 1
            if limit and count >= limit:
                break

    def _read_lines_reversed(self) -> list[str]:
        """Read file lines in reverse order (most recent first)."""
        if not self.path.exists():
            return []

        with open(self.path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        return lines[::-1]

    def count(self) -> int:
        """Return the total number of entries in the store."""
        if self._entry_count is not None:
            return self._entry_count

        if not self.path.exists():
            return 0

        with open(self.path, "r", encoding="utf-8") as f:
            self._entry_count = sum(1 for line in f if line.strip())

        return self._entry_count

    def redo_rate(self) -> float:
        """
        Calculate the REDO rate across all entries.

        Returns:
            A float between 0.0 and 1.0 representing the fraction of
            entries that resulted in REDO.
        """
        total = 0
        redos = 0

        for entry in self.entries(limit=None):
            total += 1
            if entry.get("verdict") == EffortVerdict.REDO.value:
                redos += 1

        if total == 0:
            return 0.0
        return redos / total

    def principles(self) -> list[str]:
        """
        Extract all non-empty principle strings from entries.

        Returns:
            Deduplicated list of principles violated.
        """
        seen: set[str] = set()
        result: list[str] = []
        for entry in self.entries(limit=None):
            principle = entry.get("principle") or ""
            if principle and principle not in seen:
                seen.add(principle)
                result.append(principle)
        return result

    def entries_by_category(self, category: str) -> list[MemoryEntry]:
        """
        Get all entries for a specific category.

        Args:
            category: Category to filter by (e.g., "shortcut", "verification").

        Returns:
            List of MemoryEntry objects for that category.
        """
        return [
            MemoryEntry.from_dict(e)
            for e in self.entries(category_filter=category)
        ]

    def entries_by_verdict(self, verdict: str) -> list[MemoryEntry]:
        """
        Get all entries for a specific verdict.

        Args:
            verdict: Verdict to filter by (done/redo/fail).

        Returns:
            List of MemoryEntry objects for that verdict.
        """
        ev = EffortVerdict(verdict)
        return [
            MemoryEntry.from_dict(e)
            for e in self.entries(verdict_filter=ev)
        ]

    def stats(self) -> dict:
        """
        Get comprehensive statistics about the memory store.

        Returns:
            Dict with total, verdict counts, application stats.
        """
        total = 0
        verdict_counts: dict[str, int] = {"done": 0, "redo": 0, "fail": 0}
        applied_count = 0
        applied_correctly_count = 0

        for entry in self.entries(limit=None):
            total += 1
            v = entry.get("verdict", "unknown")
            if v in verdict_counts:
                verdict_counts[v] += 1
            if entry.get("was_applied"):
                applied_count += 1
                if entry.get("applied_correctly"):
                    applied_correctly_count += 1

        return {
            "total": total,
            "done": verdict_counts["done"],
            "redo": verdict_counts["redo"],
            "fail": verdict_counts["fail"],
            "applied": applied_count,
            "applied_correctly": applied_correctly_count,
            "redo_rate": verdict_counts["redo"] / total if total > 0 else 0.0,
            "application_rate": applied_count / total if total > 0 else 0.0,
            "fix_rate": (
                applied_correctly_count / applied_count
                if applied_count > 0
                else 0.0
            ),
        }

    # -------------------------------------------------------------------------
    # Deduplication
    # -------------------------------------------------------------------------

    def is_duplicate(self, task_description: str) -> bool:
        """
        Check if a task with the same hash was recently evaluated.

        Uses a simple sliding window: if a task with the same hash
        exists in the last 50 entries, it is considered duplicate.

        Args:
            task_description: The task description to check.

        Returns:
            True if the task appears to be a duplicate.
        """
        task_hash = self._hash_task(task_description)

        for entry in self.entries(limit=50):
            if entry.get("task_hash") == task_hash:
                return True

        return False

    def retry_count_for(self, task_description: str) -> int:
        """
        Get the retry count for a task description.

        Args:
            task_description: The task to look up.

        Returns:
            The number of times this task has been retried.
        """
        task_hash = self._hash_task(task_description)

        for entry in self.entries(limit=None):
            if entry.get("task_hash") == task_hash:
                return entry.get("retry_count", 0)

        return 0

    # -------------------------------------------------------------------------
    # Consolidation
    # -------------------------------------------------------------------------

    def should_consolidate(self) -> bool:
        """
        Returns True if consolidation should be triggered.

        Consolidation is triggered when:
        - Entry count exceeds threshold (20)
        - 24 hours have passed since last consolidation
        """
        if self.count() >= self._consolidation_threshold:
            return True

        if self._last_consolidation is None:
            return self.count() > 0

        elapsed = datetime.now(timezone.utc) - self._last_consolidation
        return elapsed >= self._consolidation_interval

    def consolidate(self) -> dict:
        """
        Consolidate entries into a summary and reset the store.

        Consolidation produces a summary of recent patterns:
        - REDO rate
        - Most common issues
        - Verdict distribution
        - Most problematic categories

        Returns:
            A summary dictionary of consolidated statistics.
        """
        total = 0
        verdict_counts: dict[str, int] = {}
        issue_counts: dict[str, int] = {}
        category_counts: dict[str, int] = {}
        applied_count = 0

        for entry in self.entries(limit=None):
            total += 1
            v = entry.get("verdict", "unknown")
            verdict_counts[v] = verdict_counts.get(v, 0) + 1

            for issue in entry.get("issues", []):
                issue_counts[issue] = issue_counts.get(issue, 0) + 1

            cat = entry.get("category", "unknown")
            category_counts[cat] = category_counts.get(cat, 0) + 1

            if entry.get("was_applied"):
                applied_count += 1

        summary = {
            "consolidated_at": datetime.now(timezone.utc).isoformat(),
            "total_entries": total,
            "verdict_distribution": verdict_counts,
            "issue_frequency": issue_counts,
            "category_distribution": category_counts,
            "redo_rate": verdict_counts.get(EffortVerdict.REDO.value, 0) / total if total > 0 else 0.0,
            "application_rate": applied_count / total if total > 0 else 0.0,
        }

        # Reset: archive the file
        if self.path.exists():
            import uuid

            archive_name = self.path.with_suffix(
                f".archive.{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4]}.jsonl"
            )
            self.path.replace(archive_name)

        self._entry_count = 0
        self._last_consolidation = datetime.now(timezone.utc)

        return summary

    # -------------------------------------------------------------------------
    # Utilities
    # -------------------------------------------------------------------------

    @staticmethod
    def _hash_task(task_description: str) -> str:
        """Generate a SHA-256 hash of a task description."""
        return hashlib.sha256(task_description.encode("utf-8")).hexdigest()[:16]

    def gc(self, keep_recent: int = 100) -> int:
        """
        Garbage-collect old archive files.

        Args:
            keep_recent: Number of recent archive files to keep.

        Returns:
            Number of archive files deleted.
        """
        if not self.path.parent.exists():
            return 0

        pattern = re.escape(self.path.stem) + r"\.archive\.\d{14}\.jsonl"
        archives = sorted(
            self.path.parent.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        deleted = 0
        for archive in archives[keep_recent:]:
            archive.unlink(missing_ok=True)
            deleted += 1

        return deleted
