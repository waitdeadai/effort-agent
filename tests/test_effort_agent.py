"""Basic tests for effort-agent."""

import pytest
from pathlib import Path
import tempfile
import os

from effort_agent import EffortAgent, EffortConfig, EffortVerdict, EffortMemory
from effort_agent.core.verdict import EffortVerdict as EV
from effort_agent.evaluators import ShortcutDetector, VerificationEnforcer, IterationTracker
from effort_agent.models import EffortSpec


class TestEffortConfig:
    """Tests for EffortConfig."""

    def test_default_config(self):
        config = EffortConfig()
        assert config.enabled is False
        assert config.level is None
        assert config.min_drafts == 2

    def test_level_preset_thorough(self):
        config = EffortConfig(enabled=True, level="thorough")
        assert config.min_drafts == 2
        assert config.always_verify is True
        assert config.no_shortcuts is True

    def test_level_preset_efficient(self):
        config = EffortConfig(enabled=True, level="efficient")
        assert config.min_drafts == 1
        assert config.always_verify is False
        assert config.no_shortcuts is False

    def test_level_preset_exhaustive(self):
        config = EffortConfig(enabled=True, level="exhaustive")
        assert config.min_drafts == 3
        assert config.always_verify is True

    def test_level_preset_perfectionist(self):
        config = EffortConfig(enabled=True, level="perfectionist")
        assert config.min_drafts == 4


class TestShortcutDetector:
    """Tests for ShortcutDetector."""

    def setup_method(self):
        self.detector = ShortcutDetector()

    def test_detects_good_enough(self):
        issues, _ = self.detector.detect("This is good enough.", fail_on_good_enough=True)
        assert "good_enough_language" in issues

    def test_detects_should_work(self):
        issues, _ = self.detector.detect("This should work fine.", fail_on_good_enough=True)
        assert "good_enough_language" in issues

    def test_detects_single_pass(self):
        issues, _ = self.detector.detect("Done.", fail_on_single_pass=True)
        assert "single_pass" in issues

    def test_detects_complete(self):
        issues, _ = self.detector.detect("Complete.", fail_on_single_pass=True)
        assert "single_pass" in issues

    def test_detects_vague_copy(self):
        issues, _ = self.detector.detect("We help you transform your business.")
        assert "vague_copy" in issues

    def test_detects_assumptions(self):
        issues, _ = self.detector.detect("Assume it will work correctly.")
        assert "assumptions" in issues

    def test_clean_text_passes(self):
        issues, _ = self.detector.detect(
            "Implemented JWT authentication with proper error handling and comprehensive tests."
        )
        assert len(issues) == 0


class TestIterationTracker:
    """Tests for IterationTracker."""

    def test_increment_counts(self):
        tracker = IterationTracker(config=EffortConfig(min_drafts=2))
        key = tracker.task_key("Test task")

        assert tracker.get_count(key) == 0
        tracker.increment(key)
        assert tracker.get_count(key) == 1
        tracker.increment(key)
        assert tracker.get_count(key) == 2

    def test_evaluate_passes_at_min_drafts(self):
        tracker = IterationTracker(config=EffortConfig(min_drafts=2))
        key = tracker.task_key("Test task")

        tracker.increment(key)
        tracker.increment(key)

        passed, _, count = tracker.evaluate(key, "Test task")
        assert passed is True
        assert count == 2

    def test_evaluate_fails_below_min_drafts(self):
        tracker = IterationTracker(config=EffortConfig(min_drafts=2))
        key = tracker.task_key("Test task")

        tracker.increment(key)

        passed, _, count = tracker.evaluate(key, "Test task")
        assert passed is False
        assert count == 1


class TestVerificationEnforcer:
    """Tests for VerificationEnforcer."""

    def test_requires_verification_when_enabled(self):
        enforcer = VerificationEnforcer(config=EffortConfig(enabled=True, always_verify=True))

        class EmptyResult:
            verification_commands = []

        passed, _ = enforcer.evaluate(EmptyResult())
        assert passed is False

    def test_passes_with_substantive_commands(self):
        enforcer = VerificationEnforcer(config=EffortConfig(enabled=True, always_verify=True))

        class GoodResult:
            verification_commands = ["pytest tests/ -v"]

        passed, reasoning = enforcer.evaluate(GoodResult())
        assert passed is True

    def test_disabled_passes_without_commands(self):
        enforcer = VerificationEnforcer(config=EffortConfig(enabled=True, always_verify=False))

        class EmptyResult:
            verification_commands = []

        passed, _ = enforcer.evaluate(EmptyResult())
        assert passed is True


class TestEffortMemory:
    """Tests for EffortMemory."""

    def test_append_and_count(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.memory"
            mem = EffortMemory(path=path)

            entry_id = mem.append("Test task", EV.DONE, "Passed", [])
            assert entry_id.startswith("em-")
            assert mem.count() == 1

            entry_id2 = mem.append("Test task 2", EV.REDO, "Failed", ["single_pass"])
            assert mem.count() == 2

    def test_redo_rate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.memory"
            mem = EffortMemory(path=path)

            mem.append("Task 1", EV.DONE, "Passed", [])
            mem.append("Task 2", EV.DONE, "Passed", [])
            mem.append("Task 3", EV.REDO, "Failed", ["single_pass"])

            assert mem.redo_rate() == pytest.approx(1 / 3)

    def test_is_duplicate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.memory"
            mem = EffortMemory(path=path)

            mem.append("Build auth module", EV.DONE, "Passed", [])

            assert mem.is_duplicate("Build auth module") is True
            assert mem.is_duplicate("Build different module") is False


class TestEffortSpec:
    """Tests for EffortSpec parsing."""

    def test_parses_minimal(self):
        spec = EffortSpec.from_markdown("""# Effort — Test Project

## 1. Process Philosophy
Thorough work required.

## 2. Verification Requirements
- All code must be tested

## 3. Iteration Standards
- Minimum drafts per task: 2
""")
        assert spec.project_name == "Test Project"
        assert spec.iteration_standards.min_drafts == 2

    def test_parses_all_sections(self):
        spec = EffortSpec.from_markdown("""# Effort — Full Example

## 1. Process Philosophy
No shortcuts allowed.

## 2. Verification Requirements
- All code must be tested
- All docs must be reviewed

## 3. Iteration Standards
- Minimum drafts per task: 3
- Research MUST precede implementation

## 4. Forbidden Shortcuts
- Good enough language
- Single-pass completion

## 5. Effort Levels
| Level | Min Drafts | Always Verify | No Shortcuts |
|-------|-----------|--------------|--------------|
| efficient | 1 | false | false |
| thorough | 2 | true | true |
""")
        assert spec.project_name == "Full Example"
        assert spec.iteration_standards.min_drafts == 3
        assert spec.verification_requirements.requirements == ["All code must be tested", "All docs must be reviewed"]
        assert len(spec.effort_levels) >= 2


class TestEffortAgent:
    """Tests for the main EffortAgent."""

    def test_disabled_returns_done(self):
        agent = EffortAgent(config=EffortConfig(enabled=False))

        class AnyResult:
            verification_commands = []
            text = ""

        result = agent.evaluate("Any task", AnyResult())
        assert result.verdict == EV.DONE

    def test_single_draft_redo(self):
        agent = EffortAgent(config=EffortConfig(enabled=True, level="thorough"))

        class GoodResult:
            verification_commands = ["pytest -v"]
            text = "Implemented auth."

        result = agent.evaluate(
            task="Build auth module",
            agent_result=GoodResult(),
        )
        assert result.verdict == EV.REDO
        assert "insufficient_drafts" in result.issues

    def test_two_drafts_done(self):
        agent = EffortAgent(config=EffortConfig(enabled=True, level="thorough"))

        class GoodResult:
            verification_commands = ["pytest -v"]
            text = "Implemented auth."

        # Pre-seed 2 drafts
        key = agent.iteration_tracker.task_key("Build auth module", None)
        agent.iteration_tracker.increment(key)
        agent.iteration_tracker.increment(key)

        result = agent.evaluate(
            task="Build auth module",
            agent_result=GoodResult(),
        )
        assert result.verdict == EV.DONE

    def test_shortcut_triggers_redo(self):
        agent = EffortAgent(config=EffortConfig(enabled=True, level="thorough"))

        class BadResult:
            verification_commands = ["pytest -v"]
            text = "Good enough for now."

        key = agent.iteration_tracker.task_key("Task", None)
        agent.iteration_tracker.increment(key)
        agent.iteration_tracker.increment(key)

        result = agent.evaluate(task="Task", agent_result=BadResult())
        assert result.verdict == EV.REDO
        assert "good_enough_language" in result.issues
