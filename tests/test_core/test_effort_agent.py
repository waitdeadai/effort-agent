"""tests/test_core/test_effort_agent.py — EffortAgent core tests."""
from __future__ import annotations

import pytest
from effort_agent import EffortAgent, EffortConfig, EffortVerdict

class TestEffortAgentDisabled:
    def test_disabled_returns_done(self, disabled_agent):
        class AnyResult:
            verification_commands = []
            text = ""

        result = disabled_agent.evaluate("Any task", AnyResult())
        assert result.verdict == EffortVerdict.DONE
        assert "disabled" in result.reasoning.lower()

class TestEffortAgentEvaluate:
    def test_single_draft_triggers_redo(self):
        agent = EffortAgent(config=EffortConfig(enabled=True, level="thorough"))

        class GoodResult:
            verification_commands = ["pytest -v"]
            text = "Implemented auth."

        result = agent.evaluate(
            task="Build auth module",
            agent_result=GoodResult(),
        )
        assert result.verdict == EffortVerdict.REDO
        assert "insufficient_drafts" in result.issues

    def test_two_drafts_passes(self):
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
        assert result.verdict == EffortVerdict.DONE

    def test_shortcut_detected_triggers_redo(self):
        agent = EffortAgent(config=EffortConfig(enabled=True, level="thorough"))

        class BadResult:
            verification_commands = ["pytest -v"]
            text = "Good enough for now."

        key = agent.iteration_tracker.task_key("Task", None)
        agent.iteration_tracker.increment(key)
        agent.iteration_tracker.increment(key)

        result = agent.evaluate(task="Task", agent_result=BadResult())
        assert result.verdict == EffortVerdict.REDO
        assert "good_enough_language" in result.issues

    def test_verdict_enum_values(self):
        assert EffortVerdict.DONE.value == "done"
        assert EffortVerdict.REDO.value == "redo"
        assert EffortVerdict.FAIL.value == "fail"

    def test_memory_recorded(self, effort_agent_with_memory):
        class Result:
            verification_commands = ["pytest -v"]
            text = "Code."

        key = effort_agent_with_memory.iteration_tracker.task_key("Task", None)
        effort_agent_with_memory.iteration_tracker.increment(key)
        effort_agent_with_memory.iteration_tracker.increment(key)

        result = effort_agent_with_memory.evaluate(
            task="Task", agent_result=Result()
        )
        assert result.verdict == EffortVerdict.DONE
