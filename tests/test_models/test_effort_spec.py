"""tests/test_models/test_effort_spec.py — EffortSpec parsing tests."""
from __future__ import annotations

import pytest
from effort_agent.models.effort_spec import EffortSpec

class TestEffortSpecMinimal:
    def test_parses_minimal(self):
        spec = EffortSpec.from_markdown("""# Effort — Test

## 1. Process Philosophy
Thorough work required.

## 2. Verification Requirements
- All code must be tested

## 3. Iteration Standards
- Minimum drafts per task: 2
""")
        assert spec.project_name == "Test"
        assert spec.iteration_standards.min_drafts == 2

    def test_parses_project_name(self):
        spec = EffortSpec.from_markdown("# Effort — My Project\n## 1. Process Philosophy\nWork.")
        assert "My Project" in spec.project_name

class TestEffortSpecAllSections:
    def test_parses_all_sections(self):
        spec = EffortSpec.from_markdown("""# Effort — Full Example

## 1. Process Philosophy
No shortcuts.

## 2. Verification Requirements
- All code must be tested

## 3. Iteration Standards
- Minimum drafts per task: 3

## 4. Forbidden Shortcuts
- Good enough language
- Single-pass

## 5. Effort Levels
| Level | Min Drafts | Always Verify | No Shortcuts |
|-------|-----------|--------------|--------------|
| thorough | 2 | true | true |
""")
        assert spec.iteration_standards.min_drafts == 3
        assert len(spec.effort_levels) >= 1
