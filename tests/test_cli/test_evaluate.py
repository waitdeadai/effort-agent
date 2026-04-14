"""tests/test_cli/test_evaluate.py — effort evaluate CLI tests."""
from __future__ import annotations

import pytest
from click.testing import CliRunner
from effort_agent.cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


class TestEvaluate:
    def test_evaluate_returns_verdict(self, runner):
        """effort evaluate returns a verdict."""
        result = runner.invoke(cli, [
            "evaluate",
            "--task", "Build auth module",
            "--level", "thorough",
        ])
        assert result.exit_code == 0
        assert "VERDICT" in result.output

    def test_evaluate_verdict_only(self, runner):
        """--verdict-only only prints the verdict."""
        result = runner.invoke(cli, [
            "evaluate",
            "--task", "Build auth module",
            "--verdict-only",
        ])
        assert result.exit_code == 0
        output = result.output.strip()
        assert output in ["DONE", "REDO", "FAIL"]

    def test_evaluate_shortcut_detected(self, runner):
        """Task with shortcut language triggers REDO."""
        result = runner.invoke(cli, [
            "evaluate",
            "--task", "Good enough for now. Done.",
            "--level", "thorough",
        ])
        assert result.exit_code == 0
        assert "REDO" in result.output
