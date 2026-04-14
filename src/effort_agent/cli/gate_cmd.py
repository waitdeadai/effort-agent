"""effort gate — CI/CD process integrity gate."""
from __future__ import annotations

import click
from effort_agent import EffortAgent, EffortConfig, EffortVerdict

@click.command()
@click.option("--level", type=str, default="thorough", help="Effort level: efficient/thorough/exhaustive/perfectionist.")
@click.option("--files", type=str, default=None, help="Comma-separated list of files to scan.")
@click.option("--task", type=str, default="CI gate check", help="Task description.")
@click.pass_context
def gate(ctx: click.Context, level: str, files: str | None, task: str) -> None:
    """CI/CD gate: run effort evaluation and exit non-zero if REDO/FAIL verdicts.

    Use in CI pipelines:
        effort gate --files "auth.py,main.py" || exit 1
    """
    project_root = ctx.obj["project_root"]
    config = EffortConfig(enabled=True, level=level)
    agent = EffortAgent(config=config)

    file_list: list[str] = []
    file_contents: dict[str, str] = {}

    if files:
        for rel_path in files.split(","):
            rel_path = rel_path.strip()
            full_path = project_root / rel_path
            if not full_path.exists():
                click.echo(f"Warning: {rel_path} not found, skipping.", err=True)
                continue
            content = full_path.read_text(encoding="utf-8", errors="replace")
            file_list.append(rel_path)
            file_contents[rel_path] = content

    if not file_list:
        click.echo("No files to evaluate. Gate passes by default.")
        return

    class AgentResult:
        def __init__(self):
            self.verification_commands = ["CI gate check"]
            self.text = f"Task: {task}"

    click.echo(f"Evaluating {len(file_list)} file(s)...")

    result = agent.evaluate(
        task=task,
        agent_result=AgentResult(),
        file_contents=file_contents,
    )

    click.echo(f"\n{'='*50}")
    click.echo(f"VERDICT: {result.verdict.value.upper()}")
    click.echo(f"REASONING: {result.reasoning[:100]}")
    click.echo(f"DRAFT COUNT: {result.draft_count}")
    click.echo(f"{'='*50}")

    if result.issues:
        click.echo(f"\n{len(result.issues)} issue(s):")
        for issue in result.issues[:10]:
            click.echo(f"  - {issue}")

    if result.verdict == EffortVerdict.REDO:
        click.echo("\nFAIL: REDO verdict — process shortcuts detected", err=True)
        raise SystemExit(1)
    elif result.verdict == EffortVerdict.FAIL:
        click.echo("\nFAIL: FAIL verdict — catastrophic process failure", err=True)
        raise SystemExit(1)
    else:
        click.echo("\nPASS: All effort checks cleared.")
