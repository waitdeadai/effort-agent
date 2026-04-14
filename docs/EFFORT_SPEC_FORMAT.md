# Effort Spec Format (effort.md)

The `effort.md` file is a human-readable process definition that guides the EffortAgent's evaluation. It lives in the project root and defines how thoroughly work should be done.

## Full Format

```markdown
# Effort — {project_name}

## 1. Process Philosophy
One paragraph. How thorough should execution be?
Example: "No shortcuts allowed. Every implementation requires research,
drafting, verification, and iteration. Speed is secondary to
correctness and completeness."

## 2. Verification Requirements
- All code changes MUST be verified with tests
- All UI changes MUST be verified manually
- No "should work" or "looks good" language
- Verification commands must be included in output

## 3. Iteration Standards
- Minimum drafts per task: 2
- Maximum single-pass completion: NEVER
- Review cycles before accept: 2
- Research MUST precede implementation

## 4. Forbidden Shortcuts
- "Good enough" language
- Skipped verification (no test runs)
- Single-pass completion
- Vague/generic copy
- Assumptions without verification
- Placeholder code left untested

## 5. Effort Levels
| Level | Min Drafts | Always Verify | No Shortcuts |
|-------|-----------|--------------|--------------|
| efficient | 1 | false | false |
| thorough | 2 | true | true |
| exhaustive | 3 | true | true |
| perfectionist | 4 | true | true |
```

## Section Details

### 1. Process Philosophy

One paragraph explaining the overall process philosophy. This is used as a guiding principle for evaluation and can be referenced when giving feedback.

Example:
```
This project prioritizes correctness over speed. Every feature
must pass a full research → draft → verify → iterate cycle before
being considered done. There is no "good enough" — only done or redo.
```

### 2. Verification Requirements

Bullet list of specific verification requirements. These are enforced by the `VerificationEnforcer` component.

Requirements should be:
- **Specific**: Name the type of verification (tests, manual, etc.)
- **Actionable**: State what must be done, not just what should happen
- **Verifiable**: Must be possible to detect compliance

Examples:
```
- All code changes MUST be verified with pytest
- All database migrations MUST be tested against a copy of production data
- All user-facing strings MUST be verified by a human for tone and accuracy
```

### 3. Iteration Standards

Defines the minimum number of drafts/iterations and rules about completion.

| Field | Type | Description |
|-------|------|-------------|
| Minimum drafts per task | int | Minimum draft cycles before claiming done |
| Maximum single-pass completion | NEVER / int | Whether single-pass is allowed |
| Review cycles before accept | int | Required review cycles |
| Research before implementation | bool | Whether research must precede code |

### 4. Forbidden Shortcuts

Bullet list of explicitly forbidden shortcut phrases or behaviors. These are in addition to the built-in shortcut patterns.

Each item should be:
- **Concrete**: Name the specific shortcut or phrase
- **Observable**: Can be detected in agent output

Examples:
```
- "Good enough" / "should work" / "looks good" language
- Skipped test runs (claiming tests pass without running)
- Single-pass completion (claiming done in one iteration)
- Placeholder code (TODO, FIXME, stub) left in production code
```

### 5. Effort Levels

A table defining named effort levels. Each level has:
- **Min Drafts**: Minimum draft cycles
- **Always Verify**: Whether verification is mandatory
- **No Shortcuts**: Whether shortcut language is blocked

Predefined levels:

| Level | Min Drafts | Always Verify | No Shortcuts | Use Case |
|-------|-----------|--------------|--------------|----------|
| efficient | 1 | false | false | Prototypes, exploratory work |
| thorough | 2 | true | true | Standard development |
| exhaustive | 3 | true | true | Production systems |
| perfectionist | 4 | true | true | User-facing, polished work |

## Minimal Format

A minimal effort.md can omit the table and use defaults:

```markdown
# Effort — My Project

## 1. Process Philosophy
Thorough implementation with verification. No shortcuts.

## 2. Verification Requirements
- All code must be tested

## 3. Iteration Standards
- Minimum drafts per task: 2
- Research MUST precede implementation

## 4. Forbidden Shortcuts
- "Good enough" language
- Single-pass completion
```

The parser will fill in defaults for omitted sections.

## Loading effort.md

```python
from effort_agent import EffortAgent, EffortConfig

agent = EffortAgent(
    config=EffortConfig(enabled=True),
    effort_md_path="effort.md",
)
```

Or load it explicitly:

```python
from effort_agent.models import EffortSpec

spec = EffortSpec.from_path("effort.md")
print(spec.project_name)        # "My Project"
print(spec.iteration_standards.min_drafts)  # 2
print(spec.effort_levels["thorough"].always_verify)  # True
```

## Effort Memory Format (JSONL)

The effort.memory file stores evaluation history in JSONL format. Each entry is one line of JSON:

```json
{
  "entry_id": "em-a1b2c3d4",
  "format_version": "1.0",
  "timestamp": "2026-04-13T10:30:00Z",
  "task_hash": "sha256...",           // First 16 chars of SHA-256 of task
  "task_description": "Build auth",   // Original task text
  "file_path": "auth.py",             // Primary file
  "verdict": "REDO",                  // DONE | REDO | FAIL
  "reasoning": "Single-pass detected",
  "issues": ["single_pass"],          // Issue type names
  "principle": "Never claim done after one pass",
  "category": "process",              // process | verification | shortcut | research
  "was_applied": false,               // Whether agent acted on REDO
  "retry_count": 0
}
```

### Memory Consolidation

Memory is consolidated when:
- 20+ entries accumulate
- 24 hours have passed since last consolidation
- Manual trigger via `memory.consolidate()`

Consolidation produces a summary and archives the current file.

## Example Files

See the `examples/` directory for complete examples:
- `minimal/effort.md` — Minimal effort.md
- `full-featured/effort.md` — Complete effort.md with all sections
- `full-featured/effort.memory` — Example JSONL memory file
