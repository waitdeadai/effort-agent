"""effort lint — validate an effort.md file."""
from __future__ import annotations

import click
from effort_agent.models.effort_spec import EffortSpec

@click.command()
@click.pass_context
def lint(ctx: click.Context) -> None:
    """Validate the effort.md file in the project root.

    Checks for required sections and valid format.
    """
    project_root = ctx.obj["project_root"]
    effort_md = project_root / "effort.md"

    if not effort_md.exists():
        click.echo("effort.md not found. Run 'effort init' first.", err=True)
        raise SystemExit(1)

    try:
        content = effort_md.read_text(encoding="utf-8", errors="replace")
        spec = EffortSpec.from_markdown(content)
    except Exception as e:
        click.echo(f"effort.md parse error: {e}", err=True)
        raise SystemExit(1)

    issues = []

    if not spec.process_philosophy or len(spec.process_philosophy.text.strip()) < 10:
        issues.append("Section 'process_philosophy' is empty or too short")
    if not spec.verification_requirements or not spec.verification_requirements.requirements:
        issues.append("Section 'verification_requirements' is missing")
    if not spec.iteration_standards:
        issues.append("Section 'iteration_standards' is missing")

    if issues:
        for issue in issues:
            click.echo(f"  - {issue}", err=True)
        raise SystemExit(1)
    else:
        click.echo("effort.md is valid.")
        click.echo(f"  Project: {spec.project_name}")
        click.echo(f"  Min drafts: {spec.iteration_standards.min_drafts if spec.iteration_standards else 'not set'}")
