# Getting Started with effort-agent

## What is effort-agent?

**effort-agent** answers one question: *"Did you do the work?"*

It enforces **process integrity** in agentic workflows by detecting shortcuts like:
- "Good enough" / "Should work" language
- Single-pass completion ("Done.", "Complete.")
- Skipped verification (no test runs)
- Missing pre-code research
- Vague or placeholder content

It complements **taste-agent** (which asks "does it look right?") by focusing on whether the work was done thoroughly, not just whether the output looks good.

## Installation

```bash
pip install effort-agent
```

Or from source:

```bash
cd effort-agent
pip install -e .
```

## Quick Start

### 1. Basic Usage

```python
from effort_agent import EffortAgent, EffortConfig, EffortVerdict

# Create config (or load from effort.md)
config = EffortConfig(
    enabled=True,
    level="thorough",      # efficient | thorough | exhaustive | perfectionist
    always_verify=True,    # Require verification evidence
    no_shortcuts=True,     # Block shortcut language
    min_drafts=2,          # Minimum draft/iteration cycles
)

# Initialize agent
agent = EffortAgent(config=config)

# Your agent's result object (must have verification_commands)
class MyResult:
    verification_commands = ["pytest tests/ -v"]
    text = "Built auth module with JWT. Done."

result = agent.evaluate(
    task="Build JWT authentication module",
    agent_result=MyResult(),
    file_contents={"auth.py": "..."},
)

if result.verdict == EffortVerdict.REDO:
    print(f"REDO: {result.reasoning}")
    # Feed back to your agent
elif result.verdict == EffortVerdict.DONE:
    print("Work meets effort standards.")
```

### 2. With effort.md

Create an `effort.md` file in your project root:

```markdown
# Effort — My Project

## 1. Process Philosophy
No shortcuts allowed. Every implementation requires research,
drafting, verification, and iteration. Speed is secondary to
correctness and completeness.

## 2. Verification Requirements
- All code changes MUST be verified with tests
- All UI changes MUST be verified manually
- No "should work" or "looks good" language

## 3. Iteration Standards
- Minimum drafts per task: 2
- Maximum single-pass completion: NEVER
- Research MUST precede implementation

## 4. Forbidden Shortcuts
- "Good enough" language
- Skipped verification
- Single-pass completion
- Vague/generic copy

## 5. Effort Levels
| Level | Min Drafts | Always Verify | No Shortcuts |
|-------|-----------|--------------|--------------|
| efficient | 1 | false | false |
| thorough | 2 | true | true |
| exhaustive | 3 | true | true |
| perfectionist | 4 | true | true |
```

Load it:

```python
agent = EffortAgent(
    config=EffortConfig(enabled=True),
    effort_md_path="effort.md",
)
```

### 3. With ForgeGod

```python
from effort_agent.integration import ForgeGodEffortIntegrator

integrator = ForgeGodEffortIntegrator(
    forgegod=my_forgegod_instance,
    effort_md_path="/opt/forgegod/effort.md",
)

# Pre-implementation check
pre = integrator.pre_implementation_check(task="Build auth module")
if pre.verdict != EffortVerdict.DONE:
    return pre  # Don't start coding

# After coding
post = integrator.post_implementation_check(
    task="Build auth module",
    agent_result=forgegod_result,
    file_contents=changed_files,
)
if post.verdict == EffortVerdict.REDO:
    forgegod.reflection_loop.add_feedback(...)
```

## Effort Levels

| Level | Min Drafts | Verify | Shortcuts | Use Case |
|-------|-----------|--------|-----------|----------|
| **efficient** | 1 | Optional | Allowed | Prototypes, spikes |
| **thorough** | 2 | Required | Blocked | Standard development |
| **exhaustive** | 3 | Required | Blocked | Production, safety-critical |
| **perfectionist** | 4 | Required | Blocked | User-facing, polished work |

## EffortResult

The `evaluate()` method returns an `EffortResult`:

```python
@dataclass
class EffortResult:
    verdict: EffortVerdict          # DONE / REDO / FAIL
    reasoning: str                  # Why this verdict
    issues: list[str]              # Specific issues found
    task_description: str
    file_path: str
    effort_level: str               # "thorough", etc.
    verification_evidence_found: bool
    draft_count: int               # Drafts completed
    shortcut_phrases_found: list[str]
    timestamp: str
    category: str                  # "process", "verification", "shortcut", "research"
```

## Effort Verdict

| Verdict | Meaning | Action |
|---------|---------|--------|
| **DONE** | Work meets effort standards | Proceed |
| **REDO** | Shortcuts detected | Return to agent with issues |
| **FAIL** | Catastrophic failure | Halt (e.g., missing effort.md when required) |

## Configuration Reference

```python
class EffortConfig:
    enabled: bool = False                  # Master kill-switch
    level: str = "thorough"                # Named preset
    min_drafts: int = 2                    # Minimum draft cycles
    always_verify: bool = True             # Require verification evidence
    no_shortcuts: bool = True              # Block shortcut language
    shortcuts_blocked: list[str] = []      # Custom shortcut phrases
    research_before_code: bool = True       # Enforce pre-code research
    max_compaction_turns: int = 999        # Context compaction threshold
    retry_on_failure: bool = True          # Allow REDO retries
    require_effort_md: bool = False        # Fail if effort.md missing
    fail_on_single_pass: bool = True       # Block single-pass language
    fail_on_good_enough: bool = True       # Block "good enough" language
```

## Effort Memory

effort-agent automatically records all evaluations to `effort.memory` (JSONL):

```jsonl
{"entry_id": "em-a1b2c3d4", "timestamp": "2026-04-13T10:30:00Z",
 "task_hash": "sha256...", "task_description": "Build user auth module",
 "file_path": "auth.py", "verdict": "REDO",
 "reasoning": "Single-pass completion detected",
 "issues": ["single_pass"], "principle": "Always verify before claiming done",
 "category": "process", "was_applied": false}
```

Query the memory:

```python
# Get REDO rate
agent.memory.redo_rate()  # 0.15 = 15% REDO rate

# Check for duplicate tasks
agent.memory.is_duplicate("Build user auth module")  # True/False

# Memory summary
agent.memory_summary()
```

## Shortcut Patterns Detected

| Category | Examples |
|----------|----------|
| skipped_verification | "no need to run tests", "skip verification" |
| good_enough_language | "good enough", "should work", "looks good" |
| single_pass | "Done.", "Complete.", "All set." |
| vague_copy | "seamless", "cutting-edge", "we help you" |
| assumptions | "assume it will work", "assuming correctness" |
| placeholder_code | "// TODO", "placeholder", "will implement later" |

## Integration with taste-agent

Use both agents for complete coverage:

```python
from taste_agent import TasteAgent
from effort_agent import EffortAgent

taste = TasteAgent(config=TasteConfig(...))
effort = EffortAgent(config=EffortConfig(...))

# Run both evaluations
taste_result = taste.evaluate(task=task, output=output)
effort_result = effort.evaluate(task=task, agent_result=result)

if taste_result.verdict == TasteVerdict.REDO or effort_result.verdict == EffortVerdict.REDO:
    # Return to agent with combined feedback
    feedback = {
        "taste": taste_result.issues,
        "effort": effort_result.issues,
    }
```
