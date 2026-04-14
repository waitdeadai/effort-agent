"""IterationTracker — tracks draft counts per task and enforces minimums."""

import hashlib
from typing import Optional

from effort_agent.core.effort_config import EffortConfig


class IterationTracker:
    """
    Tracks draft/iteration counts per task and enforces minimums.

    The iteration count is a proxy for thoroughness. A task completed
    in a single pass without revision is a red flag for shortcut behavior.

    Tracking is done in-memory (for a session) and optionally persisted
    to an external store via the store parameter.
    """

    def __init__(
        self,
        config: Optional[EffortConfig] = None,
        store: Optional["IterationStore"] = None,
    ):
        """
        Initialize the IterationTracker.

        Args:
            config: EffortConfig controlling min_drafts.
            store: Optional persistence layer for iteration counts.
        """
        self.config = config or EffortConfig()
        self.store = store
        self._draft_counts: dict[str, int] = {}
        self._revision_markers: dict[str, list[str]] = {}

    def task_key(self, task_description: str, file_path: Optional[str] = None) -> str:
        """
        Generate a stable key for a task.

        Args:
            task_description: The task description.
            file_path: Optional file path to disambiguate.

        Returns:
            A SHA-256 based hash key for the task.
        """
        raw = f"{task_description}|{file_path or ''}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def increment(self, task_key: str) -> int:
        """
        Increment the draft count for a task.

        Call this each time the agent produces a new draft/output
        for the given task.

        Args:
            task_key: The task key from task_key().

        Returns:
            The new draft count after incrementing.
        """
        current = self._draft_counts.get(task_key, 0) + 1
        self._draft_counts[task_key] = current

        # Persist if store is available
        if self.store:
            self.store.set(task_key, current)

        return current

    def mark_revision(self, task_key: str, revision_note: str) -> None:
        """
        Record a revision event for a task.

        Args:
            task_key: The task key.
            revision_note: A short description of what changed in this revision.
        """
        if task_key not in self._revision_markers:
            self._revision_markers[task_key] = []

        self._revision_markers[task_key].append(revision_note)

        if self.store:
            self.store.set_revisions(task_key, self._revision_markers[task_key])

    def get_count(self, task_key: str) -> int:
        """
        Get the current draft count for a task.

        Args:
            task_key: The task key.

        Returns:
            The draft count (0 if never tracked).
        """
        if self.store and task_key not in self._draft_counts:
            self._draft_counts[task_key] = self.store.get(task_key)

        return self._draft_counts.get(task_key, 0)

    def evaluate(self, task_key: str, task_description: str) -> tuple[bool, str, int]:
        """
        Evaluate whether a task meets the iteration standard.

        Args:
            task_key: The task key from task_key().
            task_description: The task description (for error messages).

        Returns:
            A tuple of (passed, reasoning, draft_count).
            passed: True if min_drafts requirement is met.
            reasoning: Human-readable explanation.
            draft_count: The current draft count for this task.
        """
        draft_count = self.get_count(task_key)
        min_drafts = self.config.min_drafts

        if draft_count < min_drafts:
            return False, (
                f"Minimum drafts not met for task. "
                f"Expected at least {min_drafts} drafts, got {draft_count}. "
                f"Complete at least {min_drafts - draft_count} more revision "
                f"cycle(s) before claiming done. "
                f"Shortcuts like single-pass completion are not acceptable."
            ), draft_count

        return True, (
            f"Iteration requirement met ({draft_count}/{min_drafts} drafts)."
        ), draft_count

    def reset(self, task_key: Optional[str] = None) -> None:
        """
        Reset draft counts.

        Args:
            task_key: If provided, reset only this task's count.
                     If None, reset all tracked counts.
        """
        if task_key:
            self._draft_counts.pop(task_key, None)
            self._revision_markers.pop(task_key, None)
            if self.store:
                self.store.delete(task_key)
        else:
            self._draft_counts.clear()
            self._revision_markers.clear()
            if self.store:
                self.store.clear()

    def summary(self) -> dict:
        """
        Return a summary of all tracked iteration data.

        Returns:
            A dict with total tasks, average draft count, etc.
        """
        counts = list(self._draft_counts.values())

        return {
            "total_tasks_tracked": len(self._draft_counts),
            "total_drafts": sum(counts),
            "average_drafts_per_task": sum(counts) / len(counts) if counts else 0.0,
            "tasks_meeting_minimum": sum(
                1 for c in counts if c >= self.config.min_drafts
            ),
            "tasks_below_minimum": sum(1 for c in counts if c < self.config.min_drafts),
            "min_drafts_required": self.config.min_drafts,
        }


# ---------------------------------------------------------------------------
# Iteration Store (optional persistence layer)
# ---------------------------------------------------------------------------


class IterationStore:
    """
    Optional persistence layer for iteration counts.

    Implement this interface to persist iteration data across sessions.
    A simple JSON file implementation is provided in memory_store/file_store.py.
    """

    def get(self, task_key: str) -> int:
        """Get the draft count for a task key."""
        raise NotImplementedError

    def set(self, task_key: str, count: int) -> None:
        """Set the draft count for a task key."""
        raise NotImplementedError

    def get_revisions(self, task_key: str) -> list[str]:
        """Get revision notes for a task key."""
        raise NotImplementedError

    def set_revisions(self, task_key: str, revisions: list[str]) -> None:
        """Set revision notes for a task key."""
        raise NotImplementedError

    def delete(self, task_key: str) -> None:
        """Delete data for a task key."""
        raise NotImplementedError

    def clear(self) -> None:
        """Clear all data."""
        raise NotImplementedError
