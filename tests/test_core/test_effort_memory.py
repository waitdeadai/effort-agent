"""tests/test_core/test_effort_memory.py — EffortMemory tests."""
from __future__ import annotations

import pytest
import json
from pathlib import Path
from effort_agent import EffortMemory, EffortVerdict
from effort_agent.core.effort_memory import MemoryEntry

@pytest.fixture
def tmp_mem():
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test.memory"

class TestEffortMemoryAppend:
    def test_append_returns_entry_id(self, tmp_mem):
        mem = EffortMemory(path=tmp_mem)
        eid = mem.append("Task", EffortVerdict.DONE, "OK", [])
        assert eid.startswith("em-")

    def test_count_increments(self, tmp_mem):
        mem = EffortMemory(path=tmp_mem)
        assert mem.count() == 0
        mem.append("Task 1", EffortVerdict.DONE, "OK", [])
        assert mem.count() == 1
        mem.append("Task 2", EffortVerdict.REDO, "Fail", ["single_pass"])
        assert mem.count() == 2

    def test_entries_yield_recent_first(self, tmp_mem):
        mem = EffortMemory(path=tmp_mem)
        mem.append("Task 1", EffortVerdict.DONE, "OK", [])
        mem.append("Task 2", EffortVerdict.REDO, "Fail", [])
        entries = list(mem.entries())
        assert len(entries) == 2
        # Most recent first
        assert entries[0]["task_description"] == "Task 2"

class TestEffortMemoryFilters:
    def test_verdict_filter(self, tmp_mem):
        mem = EffortMemory(path=tmp_mem)
        mem.append("Task 1", EffortVerdict.DONE, "OK", [])
        mem.append("Task 2", EffortVerdict.REDO, "Fail", [])
        entries = list(mem.entries(verdict_filter=EffortVerdict.REDO))
        assert len(entries) == 1
        assert entries[0]["task_description"] == "Task 2"

    def test_category_filter(self, tmp_mem):
        mem = EffortMemory(path=tmp_mem)
        mem.append("Task 1", EffortVerdict.REDO, "Fail", [], category="shortcut")
        mem.append("Task 2", EffortVerdict.REDO, "Fail", [], category="verification")
        entries = list(mem.entries(category_filter="shortcut"))
        assert len(entries) == 1

class TestEffortMemoryStats:
    def test_redo_rate_none(self, tmp_mem):
        mem = EffortMemory(path=tmp_mem)
        assert mem.redo_rate() == 0.0

    def test_redo_rate_calculation(self, tmp_mem):
        mem = EffortMemory(path=tmp_mem)
        mem.append("T1", EffortVerdict.DONE, "OK", [])
        mem.append("T2", EffortVerdict.DONE, "OK", [])
        mem.append("T3", EffortVerdict.REDO, "Fail", [])
        assert mem.redo_rate() == pytest.approx(1/3)

    def test_retry_count_for(self, tmp_mem):
        mem = EffortMemory(path=tmp_mem)
        mem.append("Build auth", EffortVerdict.REDO, "Fail", [], retry_count=1)
        assert mem.retry_count_for("Build auth") == 1
        assert mem.retry_count_for("Other task") == 0

    def test_is_duplicate(self, tmp_mem):
        mem = EffortMemory(path=tmp_mem)
        mem.append("Build auth", EffortVerdict.DONE, "OK", [])
        assert mem.is_duplicate("Build auth") is True
        assert mem.is_duplicate("Different task") is False

class TestEffortMemoryConsolidation:
    def test_should_consolidate_at_threshold(self, tmp_mem):
        mem = EffortMemory(path=tmp_mem)
        for i in range(20):
            mem.append(f"Task {i}", EffortVerdict.DONE, "OK", [])
        assert mem.should_consolidate() is True

    def test_consolidate_archives_and_resets(self, tmp_mem):
        mem = EffortMemory(path=tmp_mem)
        for i in range(3):
            mem.append(f"Task {i}", EffortVerdict.DONE, "OK", [])
        summary = mem.consolidate()
        assert summary["total_entries"] == 3
        assert mem.count() == 0


class TestMemoryEntrySlots:
    """MemoryEntry.__slots__ attribute inspection."""

    def test_slots_are_defined(self):
        """All expected slot names are present in __slots__."""
        expected = (
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
        assert MemoryEntry.__slots__ == expected

    def test_slot_instance_raises_attribute_error(self):
        """Setting an undefined slot on an instance raises AttributeError."""
        entry = MemoryEntry(
            entry_id="em-test",
            timestamp="2026-04-14T00:00:00Z",
            task_hash="abc123",
            task_description="Test task",
            file_path=None,
            verdict="done",
            reasoning="OK",
            issues=[],
        )
        with pytest.raises(AttributeError):
            entry.undefined_slot = "value"


class TestMemoryEntryToFromDict:
    """MemoryEntry.to_dict() and MemoryEntry.from_dict() round-trip."""

    def test_to_dict_contains_all_fields(self):
        """to_dict() returns all slot-backed fields."""
        entry = MemoryEntry(
            entry_id="em-abc123",
            timestamp="2026-04-14T10:00:00Z",
            task_hash="hash456",
            task_description="Fix auth bug",
            file_path="auth.py",
            verdict="redo",
            reasoning="Single-pass detected",
            issues=["single_pass"],
            principle_violated="Always verify before claiming done",
            category="shortcut",
            was_applied=True,
            applied_correctly=True,
            retry_count=1,
            why_this_matters="Verification ensures correctness",
            severity="P1",
        )
        d = entry.to_dict()
        assert d["entry_id"] == "em-abc123"
        assert d["timestamp"] == "2026-04-14T10:00:00Z"
        assert d["task_hash"] == "hash456"
        assert d["task_description"] == "Fix auth bug"
        assert d["file_path"] == "auth.py"
        assert d["verdict"] == "redo"
        assert d["reasoning"] == "Single-pass detected"
        assert d["issues"] == ["single_pass"]
        assert d["principle_violated"] == "Always verify before claiming done"
        assert d["category"] == "shortcut"
        assert d["was_applied"] is True
        assert d["applied_correctly"] is True
        assert d["retry_count"] == 1
        assert d["why_this_matters"] == "Verification ensures correctness"
        assert d["severity"] == "P1"

    def test_from_dict_restores_all_fields(self):
        """from_dict() reconstructs a MemoryEntry with all fields."""
        data = {
            "entry_id": "em-xyz789",
            "timestamp": "2026-04-14T12:00:00Z",
            "task_hash": "hashabc",
            "task_description": "Refactor DB layer",
            "file_path": "db.py",
            "verdict": "done",
            "reasoning": "All checks passed",
            "issues": [],
            "principle_violated": None,
            "category": "process",
            "was_applied": False,
            "applied_correctly": None,
            "retry_count": 0,
            "why_this_matters": "Maintainability matters",
            "severity": "P2",
        }
        entry = MemoryEntry.from_dict(data)
        assert entry.entry_id == "em-xyz789"
        assert entry.timestamp == "2026-04-14T12:00:00Z"
        assert entry.task_hash == "hashabc"
        assert entry.task_description == "Refactor DB layer"
        assert entry.file_path == "db.py"
        assert entry.verdict == "done"
        assert entry.reasoning == "All checks passed"
        assert entry.issues == []
        assert entry.principle_violated is None
        assert entry.category == "process"
        assert entry.was_applied is False
        assert entry.applied_correctly is None
        assert entry.retry_count == 0
        assert entry.why_this_matters == "Maintainability matters"
        assert entry.severity == "P2"

    def test_from_dict_missing_fields_get_defaults(self):
        """from_dict() fills in defaults for missing optional fields."""
        minimal = {"entry_id": "em-min", "timestamp": "2026-04-14T00:00:00Z", "task_hash": "h", "task_description": "T", "file_path": None, "verdict": "done", "reasoning": "R", "issues": []}
        entry = MemoryEntry.from_dict(minimal)
        assert entry.principle_violated is None
        assert entry.category == "process"
        assert entry.was_applied is False
        assert entry.applied_correctly is None
        assert entry.retry_count == 0
        assert entry.why_this_matters == ""
        assert entry.severity == "P2"

    def test_round_trip_preserves_data(self):
        """to_dict(from_dict(data)) == data (modulo missing None fields)."""
        original = MemoryEntry(
            entry_id="em-rt",
            timestamp="2026-04-14T00:00:00Z",
            task_hash="rh",
            task_description="Round-trip test",
            file_path="test.py",
            verdict="fail",
            reasoning="Systematic failure",
            issues=["missing_tests", "incomplete"],
            principle_violated="Write tests first",
            category="verification",
            was_applied=False,
            applied_correctly=None,
            retry_count=2,
            why_this_matters="Quality requires testing",
            severity="P0",
        )
        restored = MemoryEntry.from_dict(original.to_dict())
        assert restored.entry_id == original.entry_id
        assert restored.timestamp == original.timestamp
        assert restored.task_hash == original.task_hash
        assert restored.task_description == original.task_description
        assert restored.verdict == original.verdict
        assert restored.issues == original.issues
        assert restored.principle_violated == original.principle_violated
        assert restored.was_applied == original.was_applied
        assert restored.applied_correctly == original.applied_correctly
        assert restored.retry_count == original.retry_count
        assert restored.why_this_matters == original.why_this_matters
        assert restored.severity == original.severity


class TestMemoryEntryRepr:
    """MemoryEntry.__repr__() formatting."""

    def test_repr_shows_verdict_and_task(self):
        """__repr__ includes verdict and (truncated) task description."""
        entry = MemoryEntry(
            entry_id="em-repr",
            timestamp="2026-04-14T00:00:00Z",
            task_hash="hash",
            task_description="This is a very long task description that gets truncated",
            file_path=None,
            verdict="redo",
            reasoning="",
            issues=[],
        )
        r = repr(entry)
        assert "redo" in r
        assert "MemoryEntry(" in r
        assert "applied=" in r

    def test_repr_shows_applied_flag(self):
        """__repr__ includes the applied flag."""
        entry = MemoryEntry(
            entry_id="em-applied",
            timestamp="2026-04-14T00:00:00Z",
            task_hash="hash",
            task_description="Task A",
            file_path=None,
            verdict="done",
            reasoning="",
            issues=[],
            was_applied=True,
        )
        r = repr(entry)
        assert "applied=True" in r


class TestEffortMemoryConvenienceMethods:
    """EffortMemory.principles(), entries_by_category(), entries_by_verdict(), stats()."""

    def test_principles_returns_distinct_list(self, tmp_mem):
        """principles() returns deduplicated principle strings."""
        mem = EffortMemory(path=tmp_mem)
        mem.append("Task 1", EffortVerdict.REDO, "r", [], principle_violated="Verify first")
        mem.append("Task 2", EffortVerdict.REDO, "r", [], principle_violated="Test first")
        mem.append("Task 3", EffortVerdict.REDO, "r", [], principle_violated="Verify first")  # duplicate
        assert mem.principles() == ["Verify first", "Test first"]

    def test_principles_empty_when_no_entries(self, tmp_mem):
        """principles() returns empty list for empty store."""
        mem = EffortMemory(path=tmp_mem)
        assert mem.principles() == []

    def test_entries_by_category_returns_memory_entries(self, tmp_mem):
        """entries_by_category() returns list of MemoryEntry objects."""
        mem = EffortMemory(path=tmp_mem)
        mem.append("Task 1", EffortVerdict.REDO, "r", [], category="shortcut")
        mem.append("Task 2", EffortVerdict.DONE, "ok", [], category="verification")
        mem.append("Task 3", EffortVerdict.REDO, "r", [], category="shortcut")
        results = mem.entries_by_category("shortcut")
        assert len(results) == 2
        assert all(isinstance(e, MemoryEntry) for e in results)
        assert all(e.category == "shortcut" for e in results)

    def test_entries_by_category_empty_for_unknown(self, tmp_mem):
        """entries_by_category() returns empty list for unknown category."""
        mem = EffortMemory(path=tmp_mem)
        mem.append("Task 1", EffortVerdict.REDO, "r", [], category="shortcut")
        assert mem.entries_by_category("nonexistent") == []

    def test_entries_by_verdict_returns_memory_entries(self, tmp_mem):
        """entries_by_verdict() returns list of MemoryEntry objects filtered by verdict."""
        mem = EffortMemory(path=tmp_mem)
        mem.append("Task 1", EffortVerdict.DONE, "ok", [])
        mem.append("Task 2", EffortVerdict.REDO, "r", [])
        mem.append("Task 3", EffortVerdict.FAIL, "f", [])
        results = mem.entries_by_verdict("redo")
        assert len(results) == 1
        assert isinstance(results[0], MemoryEntry)
        assert results[0].verdict == "redo"

    def test_entries_by_verdict_empty_for_known_verdict_with_no_entries(self, tmp_mem):
        """entries_by_verdict() returns empty list when verdict is valid but no entries match."""
        mem = EffortMemory(path=tmp_mem)
        mem.append("Task 1", EffortVerdict.DONE, "ok", [])
        # "fail" is a valid verdict but no entries have it
        assert mem.entries_by_verdict("fail") == []

    def test_stats_empty_store(self, tmp_mem):
        """stats() on empty store returns zeros."""
        mem = EffortMemory(path=tmp_mem)
        s = mem.stats()
        assert s["total"] == 0
        assert s["done"] == 0
        assert s["redo"] == 0
        assert s["fail"] == 0
        assert s["applied"] == 0
        assert s["applied_correctly"] == 0
        assert s["redo_rate"] == 0.0
        assert s["application_rate"] == 0.0
        assert s["fix_rate"] == 0.0

    def test_stats_counts_all_verdicts(self, tmp_mem):
        """stats() correctly counts all verdict types."""
        mem = EffortMemory(path=tmp_mem)
        mem.append("T1", EffortVerdict.DONE, "ok", [])
        mem.append("T2", EffortVerdict.REDO, "r", [])
        mem.append("T3", EffortVerdict.DONE, "ok", [])
        mem.append("T4", EffortVerdict.FAIL, "f", [])
        s = mem.stats()
        assert s["total"] == 4
        assert s["done"] == 2
        assert s["redo"] == 1
        assert s["fail"] == 1

    def test_stats_application_rates(self, tmp_mem):
        """stats() correctly computes applied/applied_correctly rates via was_applied."""
        mem = EffortMemory(path=tmp_mem)
        # Entry with was_applied=True (applied_correctly not written by append, stays None)
        mem.append("T1", EffortVerdict.REDO, "r", [], was_applied=True)
        # Entry with was_applied=True
        mem.append("T2", EffortVerdict.REDO, "r", [], was_applied=True)
        # Entry with was_applied=False
        mem.append("T3", EffortVerdict.DONE, "ok", [], was_applied=False)
        s = mem.stats()
        assert s["applied"] == 2
        # applied_correctly is 0 since append() does not write that field
        assert s["applied_correctly"] == 0
        assert s["application_rate"] == 2 / 3
        assert s["fix_rate"] == 0.0  # 0/2 since applied_correctly is never True

    def test_stats_redo_rate(self, tmp_mem):
        """stats() redo_rate matches redo_rate() method."""
        mem = EffortMemory(path=tmp_mem)
        mem.append("T1", EffortVerdict.DONE, "ok", [])
        mem.append("T2", EffortVerdict.REDO, "r", [])
        mem.append("T3", EffortVerdict.REDO, "r", [])
        s = mem.stats()
        assert s["redo_rate"] == 2 / 3


class TestEffortMemoryAppendAllFields:
    """EffortMemory.append() with all fields that are actually supported."""

    def test_append_supported_params(self, tmp_mem):
        """append() correctly stores the fields it accepts."""
        mem = EffortMemory(path=tmp_mem)
        eid = mem.append(
            "Complex task",
            EffortVerdict.REDO,
            "Needs revision",
            ["incomplete"],
            principle_violated="Do it right",
            category="quality",
            file_path="main.py",
            was_applied=True,
            retry_count=2,
        )
        assert eid.startswith("em-")
        entries = list(mem.entries())
        assert len(entries) == 1
        assert entries[0]["task_description"] == "Complex task"
        assert entries[0]["verdict"] == "redo"
        assert entries[0]["was_applied"] is True
        assert entries[0]["retry_count"] == 2
        assert entries[0]["category"] == "quality"

    def test_append_was_applied_true(self, tmp_mem):
        """append() stores was_applied=True correctly."""
        mem = EffortMemory(path=tmp_mem)
        mem.append("Task", EffortVerdict.REDO, "r", [], was_applied=True)
        entries = list(mem.entries())
        assert entries[0]["was_applied"] is True

    def test_append_was_applied_false_default(self, tmp_mem):
        """append() defaults was_applied to False when not specified."""
        mem = EffortMemory(path=tmp_mem)
        mem.append("Task", EffortVerdict.DONE, "ok", [])
        entries = list(mem.entries())
        assert entries[0]["was_applied"] is False

    def test_append_retry_count(self, tmp_mem):
        """append() stores and retrieves retry_count correctly."""
        mem = EffortMemory(path=tmp_mem)
        mem.append("Task", EffortVerdict.REDO, "r", [], retry_count=5)
        assert mem.retry_count_for("Task") == 5

    def test_append_multiple_entries_count(self, tmp_mem):
        """Multiple append() calls are all stored and retrievable."""
        mem = EffortMemory(path=tmp_mem)
        for i in range(5):
            mem.append(f"Task {i}", EffortVerdict.DONE, "ok", [])
        assert mem.count() == 5
