"""tests/test_cli/test_init.py — effort init CLI tests."""
from __future__ import annotations

import pytest
from click.testing import CliRunner
from effort_agent.cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


class TestInit:
    def test_init_creates_effort_md(self, runner, tmp_path):
        """effort init creates an effort.md file."""
        result = runner.invoke(cli, ["--project-root", str(tmp_path), "init"])
        assert result.exit_code == 0
        assert (tmp_path / "effort.md").exists()

    def test_init_idempotent(self, runner, tmp_path):
        """effort init refuses to overwrite existing file (exits 0, no error)."""
        (tmp_path / "effort.md").write_text("existing content")
        result = runner.invoke(cli, ["--project-root", str(tmp_path), "init"])
        assert result.exit_code == 0  # init gracefully refuses, no error exit
        assert "already exists" in result.output.lower()

    def test_init_with_project_name(self, runner, tmp_path):
        """effort init accepts --project-name option."""
        result = runner.invoke(cli, [
            "--project-root", str(tmp_path), "init",
            "--project-name", "My Project"
        ])
        assert result.exit_code == 0
        content = (tmp_path / "effort.md").read_text()
        assert "My Project" in content

    def test_init_content_has_sections(self, runner, tmp_path):
        """effort init creates file with required sections."""
        result = runner.invoke(cli, ["--project-root", str(tmp_path), "init"])
        assert result.exit_code == 0
        content = (tmp_path / "effort.md").read_text()
        assert "Process Philosophy" in content
        assert "Verification Requirements" in content
        assert "Iteration Standards" in content
        assert "Forbidden Shortcuts" in content
