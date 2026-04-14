# Integration Guide

## Overview

effort-agent is designed to integrate with agentic workflows, coding engines, and CI/CD pipelines. This guide covers common integration patterns.

## Integration Patterns

### 1. Direct Integration (Agentic Workflow)

The simplest pattern: call `EffortAgent.evaluate()` after each agent task.

```python
from effort_agent import EffortAgent, EffortConfig, EffortVerdict

agent = EffortAgent(config=EffortConfig(enabled=True, level="thorough"))

def process_task(task: str, agent_result) -> EffortResult:
    result = agent.evaluate(
        task=task,
        agent_result=agent_result,
        file_contents=changed_files,
    )

    if result.verdict == EffortVerdict.REDO:
        # Return to agent with specific feedback
        return {
            "action": "REDO",
            "issues": result.issues,
            "reasoning": result.reasoning,
            "principle": result.principle_violated,
        }

    if result.verdict == EffortVerdict.FAIL:
        # Hard stop
        return {
            "action": "FAIL",
            "reasoning": result.reasoning,
        }

    return {"action": "DONE", "result": result}
```

### 2. ForgeGod Integration

For the ForgeGod autonomous coding engine, use `ForgeGodEffortIntegrator`:

```python
from effort_agent.integration import ForgeGodEffortIntegrator

integrator = ForgeGodEffortIntegrator(
    forgegod=forgegod_engine,
    config=EffortConfig(
        enabled=True,
        level="exhaustive",
        always_verify=True,
        no_shortcuts=True,
        require_effort_md=False,
    ),
    effort_md_path="/opt/forgegod/effort.md",
)

# In ForgeGod's main loop:
async def execute_task(task):
    # Pre-check
    pre = integrator.pre_implementation_check(task.description)
    if pre.verdict != EffortVerdict.DONE:
        await forgegod.skip_task(reason=pre.reasoning)
        return

    # Execute
    result = await forgegod.execute(task)

    # Post-check
    post = integrator.post_implementation_check(
        task=task.description,
        agent_result=result,
        file_contents=result.changed_files,
        diff=result.diff,
    )

    if post.verdict == EffortVerdict.REDO:
        forgegod.reflection_loop.add_feedback(
            source="effort_agent",
            issues=post.issues,
            reasoning=post.reasoning,
        )
        await forgegod.retry_task()
        return

    if post.verdict == EffortVerdict.FAIL:
        forgegod.emergency_stop(reason=post.reasoning)
        return

    await forgegod.commit_changes()
```

### 3. Taste-Agent Combined Integration

Use both agents for complete quality + process coverage:

```python
from taste_agent import TasteAgent
from effort_agent import EffortAgent

taste = TasteAgent(config=TasteConfig(...))
effort = EffortAgent(config=EffortConfig(...))

def full_evaluate(task, agent_result, output):
    taste_result = taste.evaluate(task=task, output=output)
    effort_result = effort.evaluate(task=task, agent_result=agent_result)

    # Combined verdict logic
    if taste_result.verdict == TasteVerdict.FAIL or effort_result.verdict == EffortVerdict.FAIL:
        return CombinedResult(action="FAIL", ...)

    if taste_result.verdict == TasteVerdict.REDO or effort_result.verdict == EffortVerdict.REDO:
        return CombinedResult(
            action="REDO",
            taste_issues=taste_result.issues,
            effort_issues=effort_result.issues,
            reasoning=f"Taste: {taste_result.reasoning} | Effort: {effort_result.reasoning}",
        )

    return CombinedResult(action="DONE", ...)
```

### 4. CI/CD Integration

Add effort evaluation to your CI pipeline:

```yaml
# .github/workflows/ci.yml (GitHub Actions)
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run tests
        run: pytest

      - name: Check effort compliance
        run: |
          python -c "
          from effort_agent import EffortAgent, EffortConfig
          import os

          # Initialize
          agent = EffortAgent(
              config=EffortConfig(
                  enabled=True,
                  level='thorough',
                  require_effort_md=os.path.exists('effort.md'),
              ),
              effort_md_path='effort.md' if os.path.exists('effort.md') else None,
          )

          # Check git diff
          import subprocess
          diff = subprocess.check_output(['git', 'diff', '--cached']).decode()

          # Evaluate
          result = agent.evaluate(
              task=f'CI pipeline check: {os.getenv("GITHUB_REF")}',
              agent_result=SimpleResult(verification_commands=['pytest']),
              diff=diff,
          )

          if result.verdict != 'done':
              print(f'::error::Effort evaluation failed: {result.reasoning}')
              exit(1)
          "
```

### 5. Webhook/API Integration

Expose effort evaluation as an API endpoint:

```python
from fastapi import FastAPI, Header
from effort_agent import EffortAgent, EffortConfig, EffortVerdict
from pydantic import BaseModel

app = FastAPI()
agent = EffortAgent(config=EffortConfig(enabled=True))

class EvaluateRequest(BaseModel):
    task: str
    verification_commands: list[str]
    output_text: str
    file_contents: dict[str, str] = {}

@app.post("/evaluate")
def evaluate(req: EvaluateRequest, x_api_key: str = Header(...)):
    # Validate API key
    if x_api_key != os.getenv("EFFORT_API_KEY"):
        return {"error": "Invalid API key"}, 401

    class AgentResult:
        verification_commands = req.verification_commands
        text = req.output_text

    result = agent.evaluate(
        task=req.task,
        agent_result=AgentResult(),
        file_contents=req.file_contents,
    )

    return {
        "verdict": result.verdict.value,
        "reasoning": result.reasoning,
        "issues": result.issues,
        "draft_count": result.draft_count,
    }
```

## AgentResult Protocol

Your agent's result object must satisfy the `AgentResultLike` protocol:

```python
class AgentResultLike(Protocol):
    verification_commands: list[str]
    """List of verification commands that were run."""

    tests_run: Optional[bool] = None
    """Whether tests were actually run."""

    tests_passed: Optional[bool] = None
    """Whether tests passed if run."""

    manual_verification_done: Optional[bool] = None
    """Whether manual verification was performed."""
```

Minimum implementation:

```python
class MyAgentResult:
    verification_commands: list[str] = []
    text: str = ""

# Just these two fields are required for basic evaluation
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| EFFORT_AGENT_ENABLED | Enable/disable evaluation | "false" |
| EFFORT_LEVEL | Effort level | "thorough" |
| EFFORT_MEMORY_PATH | Path to JSONL memory | "effort.memory" |
| EFFORT_MD_PATH | Path to effort.md | None |

## Memory Storage

By default, effort.memory is stored as JSONL in the working directory.

For production, use `SQLiteIterationStore` for better concurrency:

```python
from effort_agent import EffortAgent
from effort_agent.memory_store import SQLiteIterationStore

store = SQLiteIterationStore("/var/lib/effort-agent/iterations.db")
agent = EffortAgent(
    config=EffortConfig(enabled=True),
    memory_path="effort.memory",  # Still used for JSONL evaluation history
)
agent.iteration_tracker.store = store  # Use SQLite for counts
```
