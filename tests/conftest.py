"""Shared pytest fixtures for effort-agent tests."""
from __future__ import annotations

import pytest
import tempfile
from pathlib import Path

from effort_agent import EffortAgent, EffortConfig, EffortVerdict, EffortMemory


@pytest.fixture
def temp_memory_path():
    """Temporary path for memory file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test.memory"


@pytest.fixture
def sample_agent_result():
    """Sample agent result with verification commands."""
    class Result:
        verification_commands = ["pytest tests/ -v"]
        text = "Implemented auth module with tests. Done."
    return Result


@pytest.fixture
def effort_agent_with_memory(temp_memory_path):
    """EffortAgent with in-memory tracking."""
    agent = EffortAgent(
        config=EffortConfig(enabled=True, level="thorough"),
        memory_path=temp_memory_path,
    )
    return agent


@pytest.fixture
def disabled_agent():
    """EffortAgent in disabled state."""
    return EffortAgent(config=EffortConfig(enabled=False))


@pytest.fixture
def runner():
    """Click CLI test runner."""
    from click.testing import CliRunner
    return CliRunner()
