"""EffortMemory — append-only JSONL store for effort evaluation history."""

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Iterator

from effort_agent.core.verdict import EffortVerdict


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
