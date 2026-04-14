"""effort evaluate — run effort evaluation on a task."""
from __future__ import annotations

import click
from effort_agent import EffortAgent, EffortConfig

@click.command()
@click.option("--task", type=str, required=True, help="Task description to evaluate.")
@click.option("--level", type=str, default="thorough", help="Effort level.")
@click.option("--verdict-only", is_flag=True, help="Only print the verdict.")
@click.pass_context
def evaluate(ctx: click.Context, task: str, level: str, verdict_only: bool) -> None:
    """Run effort evaluation on a task description.

    Returns DONE/REDO/FAIL verdict with reasoning.
    """
    config = EffortConfig(enabled=True, level=level)
    agent = EffortAgent(config=config)

    class AgentResult:
        def __init__(self):
            self.verification_commands = ["evaluated via CLI"]
            self.text = task

    result = agent.evaluate(task=task, agent_result=AgentResult())

    if verdict_only:
        click.echo(result.verdict.value.upper())
    else:
        click.echo(f"VERDICT: {result.verdict.value.upper()}")
        click.echo(f"REASONING: {result.reasoning}")
        if result.issues:
            click.echo(f"ISSUES: {', '.join(result.issues)}")
