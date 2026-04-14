"""
ForgeGod Integration — how effort-agent works with the ForgeGod agentic coding engine.

ForgeGod (forgegod.com) is an autonomous coding engine that uses a 5-ring agent
architecture with Reflexion and multi-model execution. Effort-agent integrates
with ForgeGod to enforce process integrity at each stage of the coding loop.

## Integration Points

### 1. Pre-Implementation Gate (Ring 2: Strategy)
Before ForgeGod generates code, effort-agent can verify that:
- An effort.md exists for the project
- The task has been analyzed for research requirements
- The approach has been reviewed against forbidden shortcuts

### 2. Post-Implementation Gate (Ring 3: Execution → Ring 4: Verification)
After ForgeGod produces code but before it claims done:
- Shortcut detection scans the output
- Verification enforcer checks for test runs
- Iteration tracker ensures minimum drafts

### 3. Reflexion Loop Integration (Ring 5: Self-Healing)
When ForgeGod's Reflexion module identifies issues:
- Effort verdict is stored in effort.memory (JSONL)
- REDO verdicts feed back into the next iteration
- Patterns in shortcuts feed into the self-healing rules

## ForgeGod-Specific Configuration

ForgeGod operates at "exhaustive" or "perfectionist" levels by default
for production code, and "thorough" for prototypes.

## Usage with ForgeGod

```python
from effort_agent import EffortAgent
from effort_agent.core import EffortConfig, EffortVerdict

# Initialize for ForgeGod
effort = EffortAgent(
    config=EffortConfig(
        enabled=True,
        level="exhaustive",
        always_verify=True,
        no_shortcuts=True,
        research_before_code=True,
        require_effort_md=True,
    ),
    effort_md_path="/opt/forgegod/effort.md",
)

# After each coding task
result = effort.evaluate(
    task="Implement JWT authentication module",
    agent_result=forgegod_result,
    file_contents=changed_files,
    diff=diff_output,
)

if result.verdict == EffortVerdict.REDO:
    # Feed back to ForgeGod's Reflexion
    forgegod.reflection_loop.add_feedback(
        source="effort-agent",
        issues=result.issues,
        reasoning=result.reasoning,
    )
    return result  # Don't commit — redo the task

if result.verdict == EffortVerdict.FAIL:
    # Hard stop — something is fundamentally wrong
    forgegod.emergency_stop(reason=result.reasoning)
    return result

# Commit the changes
```

## Effort Memory Analysis for ForgeGod

ForgeGod can query effort.memory to identify systematic shortcut patterns:

```python
summary = effort.memory_summary()
if summary['redo_rate'] > 0.3:
    forgegod.self_healing.learn_pattern(
        pattern="skipped_verification",
        cause="agent_rushing_to_complete",
        remedy="force_verification_step"
    )
```

## Environment Variables

- EFFORT_AGENT_ENABLED: Set to "true" to enable effort enforcement
- EFFORT_LEVEL: effort level (efficient/thorough/exhaustive/perfectionist)
- EFFORT_MEMORY_PATH: Path to effort.memory JSONL file
- EFFORT_MD_PATH: Path to project effort.md file
"""

from effort_agent import EffortAgent
from effort_agent.core import EffortConfig, EffortVerdict, EffortResult
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class ForgeGodEffortIntegrator:
    """
    Integration helper for connecting effort-agent to ForgeGod.

    This class provides ForgeGod-specific convenience methods for
    interacting with the effort agent.
    """

    def __init__(
        self,
        forgegod,
        config: Optional[EffortConfig] = None,
        effort_md_path: Optional[str | Path] = None,
    ):
        """
        Initialize the ForgeGod integrator.

        Args:
            forgegod: The ForgeGod engine instance (from clawdbot.forge).
            config: EffortConfig. Defaults to exhaustive level.
            effort_md_path: Path to the project's effort.md file.
        """
        self.forgegod = forgegod
        self.config = config or EffortConfig(
            enabled=True,
            level="exhaustive",
            always_verify=True,
            no_shortcuts=True,
            research_before_code=True,
            require_effort_md=False,  # ForgeGod has its own process
        )
        self.effort = EffortAgent(
            config=self.config,
            effort_md_path=effort_md_path,
        )

    def pre_implementation_check(self, task: str) -> EffortResult:
        """
        Run pre-implementation checks before ForgeGod starts coding.

        This verifies research was done and effort.md is loaded.

        Args:
            task: The task description.

        Returns:
            EffortResult (usually PASS with warnings, or FAIL).
        """
        # Check effort.md is loaded
        if self.config.require_effort_md and not self.effort.effort_spec:
            return EffortResult(
                verdict=EffortVerdict.FAIL,
                reasoning="effort.md required but not loaded. "
                          "ForgeGod cannot proceed without process definition.",
                task_description=task,
            )

        # Check research requirement
        # (pre-implementation means no output yet, so we just check the task)
        research_result = self.effort.research_enforcer.evaluate(
            task, "", None
        )

        if not research_result[0]:
            return EffortResult(
                verdict=EffortVerdict.REDO,
                reasoning=research_result[1],
                task_description=task,
                issues=["missing_research"],
                category="research",
            )

        return EffortResult(
            verdict=EffortVerdict.DONE,
            reasoning="Pre-implementation checks passed.",
            task_description=task,
        )

    def post_implementation_check(
        self,
        task: str,
        agent_result,
        file_contents: Optional[dict[str, str]] = None,
        diff: Optional[str] = None,
    ) -> EffortResult:
        """
        Run post-implementation checks after ForgeGod produces code.

        This is the main effort gate — if this fails, ForgeGod must redo.

        Args:
            task: The task description.
            agent_result: ForgeGod's result object.
            file_contents: Changed file contents.
            diff: Git-style diff of changes.

        Returns:
            EffortResult with verdict (DONE/REDO/FAIL).
        """
        result = self.effort.evaluate(
            task=task,
            agent_result=agent_result,
            file_contents=file_contents,
            diff=diff,
        )

        # Record in ForgeGod's reflection loop if REDO
        if result.verdict == EffortVerdict.REDO:
            self._record_redo(result)

        return result

    def _record_redo(self, result: EffortResult) -> None:
        """
        Record a REDO verdict into ForgeGod's reflection/feedback system.

        Args:
            result: The EffortResult with REDO verdict.
        """
        # This hooks into ForgeGod's Reflexion loop
        # The implementation depends on ForgeGod's internal APIs
        try:
            if hasattr(self.forgegod, "reflection_loop"):
                self.forgegod.reflection_loop.add_feedback(
                    source="effort_agent",
                    verdict="REDO",
                    issues=result.issues,
                    reasoning=result.reasoning,
                    principle=result.principle_violated,
                )
        except Exception:
            # ForgeGod integration is best-effort — don't fail if unavailable
            pass

    def effort_summary(self) -> dict:
        """
        Get a summary of effort statistics for ForgeGod's observability.

        Returns:
            A dict with effort memory and iteration statistics.
        """
        return self.effort.memory_summary()

    def is_healthy(self) -> bool:
        """
        Check if effort integration is healthy.

        Returns:
            True if the effort agent is operational.
        """
        try:
            summary = self.effort.memory_summary()
            return True
        except Exception:
            return False
