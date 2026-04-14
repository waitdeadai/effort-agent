# effort-agent

**Process Integrity Enforcer for Agentic Workflows**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

---

## The Problem

Agentic AI systems (agents, coding engines, autonomous pipelines) are great at producing output quickly. But speed often comes at the cost of **process integrity**:

- Agents claim "Done." after a single pass
- Verification steps ("tests") are skipped or assumed
- "Good enough" language creeps into output
- Research is skipped in favor of "just implement"
- Placeholder code ships as finished work

**taste-agent** answers "Does it look right?" (aesthetic/quality).
**effort-agent** answers "Did you do the work?" (process integrity).

## Quick Start

```python
from effort_agent import EffortAgent, EffortConfig, EffortVerdict

# Create and enable agent
agent = EffortAgent(
    config=EffortConfig(
        enabled=True,
        level="thorough",
        always_verify=True,
        no_shortcuts=True,
    )
)

# Your agent's result (must have verification_commands)
class MyResult:
    verification_commands = ["pytest tests/ -v"]
    text = "Implemented auth module with JWT. Done."

# Evaluate
result = agent.evaluate(
    task="Build JWT authentication module",
    agent_result=MyResult(),
    file_contents={"auth.py": "..."},
)

if result.verdict == EffortVerdict.REDO:
    print(f"REDO: {result.reasoning}")
    # Feed back to agent for revision
elif result.verdict == EffortVerdict.DONE:
    print("Work meets effort standards.")
```

## Key Features

### Shortcut Detection

Detects common shortcut language across 6 categories:

| Category | Examples |
|----------|----------|
| `skipped_verification` | "no need to run tests", "skip verification" |
| `good_enough_language` | "good enough", "should work", "looks good" |
| `single_pass` | "Done.", "Complete.", "All set." |
| `vague_copy` | "seamless", "cutting-edge", "we help you" |
| `assumptions` | "assume it will work", "assuming correctness" |
| `placeholder_code` | "// TODO", "placeholder", "stub" |

### Verification Enforcement

When `always_verify=True`, the agent **must** provide `verification_commands` in its result. Empty or placeholder commands trigger a REDO.

```python
# This triggers REDO
class BadResult:
    verification_commands = []  # Empty — no evidence of verification

# This passes
class GoodResult:
    verification_commands = ["pytest tests/ -v --tb=short"]
```

### Iteration Tracking

effort-agent tracks draft counts per task and enforces minimums:

- `efficient`: 1 draft (prototypes)
- `thorough`: 2 drafts (default, standard development)
- `exhaustive`: 3 drafts (production systems)
- `perfectionist`: 4 drafts (user-facing, polished work)

### Research Enforcement

When `research_before_code=True`, the agent must show evidence of research before implementation — search queries, doc lookups, existing code inspection.

### Effort Memory (JSONL)

All evaluations are recorded to `effort.memory` (JSONL append-only log):

```jsonl
{"entry_id": "em-a1b2c3d4", "timestamp": "2026-04-13T10:30:00Z",
 "task_description": "Build user auth module", "file_path": "auth.py",
 "verdict": "REDO", "reasoning": "Single-pass completion detected",
 "issues": ["single_pass"], "category": "process", "was_applied": false}
```

Query the memory:
```python
agent.memory.redo_rate()       # 0.15 = 15% REDO rate
agent.memory_summary()          # Full statistics
agent.memory.is_duplicate(task) # Check for repeated tasks
```

## Installation

```bash
pip install effort-agent
```

With extras:
```bash
pip install effort-agent[dev]        # Development dependencies
pip install effort-agent[sqlite]    # SQLite iteration store
```

## Configuration

```python
from effort_agent import EffortConfig

config = EffortConfig(
    enabled=True,                    # Master kill-switch
    level="thorough",                # Preset level
    min_drafts=2,                    # Minimum draft cycles
    always_verify=True,              # Require verification evidence
    no_shortcuts=True,               # Block shortcut language
    shortcuts_blocked=[],            # Custom shortcut patterns
    research_before_code=True,       # Enforce pre-code research
    require_effort_md=False,         # Fail if effort.md missing
    fail_on_single_pass=True,        # Block single-pass language
    fail_on_good_enough=True,        # Block "good enough" language
)
```

## effort.md Format

Create `effort.md` in your project root for declarative process definition:

```markdown
# Effort — My Project

## 1. Process Philosophy
No shortcuts allowed. Every implementation requires research,
drafting, verification, and iteration.

## 2. Verification Requirements
- All code changes MUST be verified with tests
- No "should work" or "looks good" language

## 3. Iteration Standards
- Minimum drafts per task: 2
- Research MUST precede implementation

## 4. Forbidden Shortcuts
- "Good enough" language
- Single-pass completion
```

Load it:
```python
agent = EffortAgent(
    config=EffortConfig(enabled=True),
    effort_md_path="effort.md",
)
```

## Integrations

### ForgeGod

```python
from effort_agent.integration import ForgeGodEffortIntegrator

integrator = ForgeGodEffortIntegrator(
    forgegod=my_forgegod_instance,
    effort_md_path="/opt/forgegod/effort.md",
)

# In ForgeGod's loop
post = integrator.post_implementation_check(
    task=task.description,
    agent_result=result,
    file_contents=result.changed_files,
)

if post.verdict == EffortVerdict.REDO:
    forgegod.reflection_loop.add_feedback(issues=post.issues)
```

See [docs/INTEGRATION.md](docs/INTEGRATION.md) for more patterns (CI/CD, FastAPI, taste-agent).

## Directory Structure

```
effort-agent/
├── LICENSE
├── README.md
├── pyproject.toml
├── src/effort_agent/
│   ├── __init__.py
│   ├── version.py
│   ├── core/
│   │   ├── effort_agent.py        # Main EffortAgent class
│   │   ├── verdict.py             # VERDICT enum
│   │   ├── effort_config.py       # EffortConfig pydantic model
│   │   ├── effort_memory.py       # JSONL memory store
│   │   └── effort_result.py       # EffortResult dataclass
│   ├── evaluators/
│   │   ├── shortcut_detector.py   # Regex pattern detector
│   │   ├── verification_enforcer.py
│   │   ├── iteration_tracker.py
│   │   └── research_enforcer.py
│   ├── prompts/
│   │   ├── effort_system.py
│   │   └── verdict_prompt.py
│   ├── models/
│   │   ├── effort_spec.py         # Parsed effort.md
│   │   └── evaluation.py          # EvaluationResult
│   ├── memory_store/
│   │   ├── sqlite_store.py
│   │   └── file_store.py
│   └── integration/
│       └── forgegod_integration.py
├── tests/
├── examples/
│   ├── minimal/effort.md
│   └── full-featured/
│       ├── effort.md
│       └── effort.memory
└── docs/
    ├── GETTING_STARTED.md
    ├── EFFORT_SPEC_FORMAT.md
    └── INTEGRATION.md
```

## Verdict Reference

| Verdict | Meaning | Agent Action |
|---------|---------|--------------|
| `DONE` | Work meets effort standards | Proceed |
| `REDO` | Shortcuts detected | Return to agent with issues |
| `FAIL` | Catastrophic failure | Halt execution |

## Dependencies

- `pydantic>=2.11` — Data validation and settings
- `httpx>=0.28` — HTTP client (for future API integrations)
- `json-repair>=0.44` — JSON repair (for corrupted memory files)

## License

Apache 2.0 — see [LICENSE](LICENSE).

---

**effort-agent** is part of the WAITDEAD system (Audit. Plan. Scale.) and complements [taste-agent](https://github.com/waitdead/taste-agent).
