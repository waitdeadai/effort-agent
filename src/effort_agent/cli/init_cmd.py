"""effort init — scaffold an effort.md file."""
from __future__ import annotations

import click
from pathlib import Path

INITIAL_EFFORT_MD = '''# Effort — {project_name}

## 1. Process Philosophy
No shortcuts allowed. Every implementation requires research,
drafting, verification, and iteration. "Done." is not a valid
completion — evidence of verification is required.

## 2. Verification Requirements
- All code changes MUST be verified with tests before claiming completion
- No "should work" or "looks good" language in code or output
- Verification commands must be substantive (not empty or placeholder)

## 3. Iteration Standards
- Minimum drafts per task: 2 (thorough level)
- Research MUST precede implementation
- Never skip the draft/iteration cycle even for "small" changes

## 4. Forbidden Shortcuts
- "Good enough" / "should work" language
- Single-pass completion ("Done.", "Complete.")
- Vague corporate copy ("seamless", "cutting-edge", "we help you")
- Assumptions stated as facts
- Placeholder / TODO code in deliverables

## 5. Effort Levels
| Level | Min Drafts | Always Verify | No Shortcuts |
|-------|-----------|--------------|--------------|
| efficient | 1 | false | false |
| thorough | 2 | true | true |
| exhaustive | 3 | true | true |
| perfectionist | 4 | true | true |
'''

@click.command()
@click.option("--project-name", type=str, default=None, help="Project name for the effort.md header.")
@click.pass_context
def init(ctx: click.Context, project_name: str | None) -> None:
    """Scaffold an effort.md file in the project root.

    Creates a default effort.md with standard process integrity rules.
    """
    project_root = ctx.obj["project_root"]
    effort_md = project_root / "effort.md"

    if effort_md.exists():
        click.echo(f"effort.md already exists at {effort_md}", err=True)
        click.echo("Refusing to overwrite existing file.", err=True)
        return

    name = project_name or project_root.name.title()
    content = INITIAL_EFFORT_MD.format(project_name=name)
    effort_md.write_text(content, encoding="utf-8")
    click.echo(f"Created {effort_md}")
