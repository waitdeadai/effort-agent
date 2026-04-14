"""
effort-agent — Process Integrity Enforcer.

A Python package that enforces process integrity in agentic workflows.
"Did you do the work?" — effort-agent checks for shortcuts, skipped verification,
single-pass completion, and "good enough" language.

Example:
    from effort_agent import EffortAgent, EffortConfig, EffortVerdict

    agent = EffortAgent(config=EffortConfig(enabled=True, level="thorough"))
    result = agent.evaluate(
        task="Build user auth module",
        agent_result=my_agent_result,
        file_contents={"auth.py": "..."},
    )

    if result.verdict == EffortVerdict.REDO:
        print(f"REDO: {result.reasoning}")

Quick Start:
    1. Create an EffortConfig (or use an effort.md file)
    2. Initialize EffortAgent with the config
    3. Call agent.evaluate() after each agent task
    4. Check result.verdict — REDO means redo the task

effort-agent complements taste-agent:
    - taste-agent: "Does it look right?" (aesthetic/quality)
    - effort-agent: "Did you do the work?" (process integrity)
"""

from effort_agent.core.effort_agent import EffortAgent
from effort_agent.core.effort_config import EffortConfig
from effort_agent.core.effort_result import EffortResult
from effort_agent.core.effort_memory import EffortMemory, MemoryEntry
from effort_agent.core.verdict import EffortVerdict

__version__ = "0.1.0"

__all__ = [
    "EffortAgent",
    "EffortConfig",
    "EffortResult",
    "EffortMemory",
    "MemoryEntry",
    "EffortVerdict",
    "__version__",
]

# CLI components
try:
    from effort_agent.cli.main import cli as cli
    from effort_agent.cli.main import main as main
    __all__.extend(["cli", "main"])
except ImportError:
    pass
