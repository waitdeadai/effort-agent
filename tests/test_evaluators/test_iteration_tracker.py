"""tests/test_evaluators/test_iteration_tracker.py — IterationTracker tests."""
from __future__ import annotations

import pytest
from effort_agent import EffortConfig
from effort_agent.evaluators.iteration_tracker import IterationTracker


class TestIterationTrackerReset:
    """IterationTracker.reset() — clears per-task or all counts."""

    def test_reset_single_task(self):
        """reset(task_key) clears only that task's count."""
        tracker = IterationTracker()
        key1 = tracker.task_key("Task A")
        key2 = tracker.task_key("Task B")
        tracker.increment(key1)
        tracker.increment(key1)
        tracker.increment(key2)
        assert tracker.get_count(key1) == 2
        assert tracker.get_count(key2) == 1
        tracker.reset(key1)
        assert tracker.get_count(key1) == 0
        assert tracker.get_count(key2) == 1

    def test_reset_all(self):
        """reset() with no argument clears all tracked counts."""
        tracker = IterationTracker()
        key1 = tracker.task_key("Task A")
        key2 = tracker.task_key("Task B")
        tracker.increment(key1)
        tracker.increment(key2)
        tracker.reset()
        assert tracker.get_count(key1) == 0
        assert tracker.get_count(key2) == 0

    def test_reset_nonexistent_task_is_safe(self):
        """reset(task_key) on an untracked key does nothing."""
        tracker = IterationTracker()
        tracker.reset("never-seen-key")
        # No error raised


class TestIterationTrackerSummary:
    """IterationTracker.summary() — returns aggregate statistics dict."""

    def test_summary_returns_dict(self):
        """summary() returns a dict with expected keys."""
        tracker = IterationTracker(config=EffortConfig(min_drafts=2))
        key1 = tracker.task_key("Task A")
        key2 = tracker.task_key("Task B")
        tracker.increment(key1)
        tracker.increment(key1)
        tracker.increment(key2)
        s = tracker.summary()
        assert isinstance(s, dict)
        assert "total_tasks_tracked" in s
        assert "total_drafts" in s
        assert "average_drafts_per_task" in s
        assert "tasks_meeting_minimum" in s
        assert "tasks_below_minimum" in s
        assert "min_drafts_required" in s

    def test_summary_values(self):
        """summary() computes correct aggregate values."""
        tracker = IterationTracker(config=EffortConfig(min_drafts=2))
        key1 = tracker.task_key("Task A")
        key2 = tracker.task_key("Task B")
        tracker.increment(key1)  # 1 — below min 2
        tracker.increment(key1)  # 2 — meets min
        tracker.increment(key2)  # 1 — below min 2
        s = tracker.summary()
        assert s["total_tasks_tracked"] == 2
        assert s["total_drafts"] == 3
        assert s["average_drafts_per_task"] == 1.5
        assert s["tasks_meeting_minimum"] == 1
        assert s["tasks_below_minimum"] == 1
        assert s["min_drafts_required"] == 2

    def test_summary_empty_tracker(self):
        """summary() on a tracker with no tasks returns zero values."""
        tracker = IterationTracker(config=EffortConfig(min_drafts=2))
        s = tracker.summary()
        assert s["total_tasks_tracked"] == 0
        assert s["total_drafts"] == 0
        assert s["average_drafts_per_task"] == 0.0
        assert s["tasks_meeting_minimum"] == 0
        assert s["tasks_below_minimum"] == 0


class TestIterationTrackerTaskKey:
    """IterationTracker.task_key() — generates stable SHA-256 based keys."""

    def test_task_key_generates_stable_key(self):
        """Same task_description + file_path always produces the same key."""
        tracker = IterationTracker()
        key1 = tracker.task_key("Build the auth module", "auth.py")
        key2 = tracker.task_key("Build the auth module", "auth.py")
        assert key1 == key2
        assert len(key1) == 16  # hexdigest[:16]

    def test_task_key_different_inputs_different_keys(self):
        """Different task_description or file_path produce different keys."""
        tracker = IterationTracker()
        key_a = tracker.task_key("Task A", "a.py")
        key_b = tracker.task_key("Task B", "a.py")
        key_c = tracker.task_key("Task A", "b.py")
        assert key_a != key_b
        assert key_a != key_c
        assert key_b != key_c

    def test_task_key_without_file_path(self):
        """task_key() works with only task_description (file_path=None)."""
        tracker = IterationTracker()
        key = tracker.task_key("Some task without file")
        assert len(key) == 16
        assert key == tracker.task_key("Some task without file")

    def test_task_key_is_hex(self):
        """task_key() returns a valid hexadecimal string."""
        tracker = IterationTracker()
        key = tracker.task_key("Any task", "file.py")
        int(key, 16)  # raises ValueError if not valid hex


class TestIterationTrackerIncrement:
    """IterationTracker.increment() — increases draft count per task."""

    def test_increment_resets_count(self):
        """increment() on a task that already has count should still accumulate."""
        tracker = IterationTracker()
        key = tracker.task_key("Task X")
        assert tracker.get_count(key) == 0
        tracker.increment(key)
        assert tracker.get_count(key) == 1
        tracker.increment(key)
        assert tracker.get_count(key) == 2
        tracker.increment(key)
        assert tracker.get_count(key) == 3

    def test_increment_returns_new_count(self):
        """increment() returns the draft count after incrementing."""
        tracker = IterationTracker()
        key = tracker.task_key("Task Y")
        assert tracker.increment(key) == 1
        assert tracker.increment(key) == 2
        assert tracker.increment(key) == 3


class TestIterationTrackerEvaluate:
    """IterationTracker.evaluate() — checks min_drafts requirement."""

    def test_evaluate_fails_below_min_drafts(self):
        """evaluate() returns (False, reason, count) when drafts < min_drafts."""
        tracker = IterationTracker(config=EffortConfig(min_drafts=2))
        key = tracker.task_key("Task Z")
        tracker.increment(key)  # 1, below min 2
        passed, reason, count = tracker.evaluate(key, "Task Z")
        assert passed is False
        assert "1" in reason
        assert "2" in reason
        assert count == 1

    def test_evaluate_passes_at_min_drafts(self):
        """evaluate() returns (True, reason, count) when drafts >= min_drafts."""
        tracker = IterationTracker(config=EffortConfig(min_drafts=2))
        key = tracker.task_key("Task W")
        tracker.increment(key)
        tracker.increment(key)  # meets min 2
        passed, reason, count = tracker.evaluate(key, "Task W")
        assert passed is True
        assert count == 2