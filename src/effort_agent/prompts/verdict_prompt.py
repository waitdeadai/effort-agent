"""Per-task evaluation prompt builder for effort evaluation."""

from typing import Optional


def build_verdict_prompt(
    task_description: str,
    agent_output: str,
    effort_config: dict,
    file_path: Optional[str] = None,
    file_contents: Optional[dict[str, str]] = None,
    diff: Optional[str] = None,
    verification_commands: Optional[list[str]] = None,
    shortcut_issues: Optional[list[str]] = None,
    shortcut_phrases: Optional[list[str]] = None,
    draft_count: int = 0,
    verification_passed: Optional[bool] = None,
    research_passed: Optional[bool] = None,
) -> str:
    """
    Build a per-task evaluation prompt for the EffortAgent.

    This prompt is fed to an LLM that acts as the effort evaluator,
    deciding whether the work meets process standards.

    Args:
        task_description: The original task description.
        agent_output: The agent's output text.
        effort_config: Dict representation of EffortConfig.
        file_path: Primary file path.
        file_contents: Dict of file paths to content.
        diff: Optional diff of changes.
        verification_commands: List of verification commands run.
        shortcut_issues: Pre-detected shortcut issue names.
        shortcut_phrases: Pre-detected shortcut phrase matches.
        draft_count: Number of drafts completed.
        verification_passed: Whether verification enforcement passed.
        research_passed: Whether research enforcement passed.

    Returns:
        A formatted string prompt for effort evaluation.
    """
    lines = [
        "# Effort Evaluation for Task",
        "",
        "## Task Description",
        task_description,
        "",
    ]

    if file_path:
        lines.extend(["## Primary File", f"`{file_path}`", ""])

    lines.extend([
        "## Agent Output",
        "```",
        agent_output[:4000] if len(agent_output) > 4000 else agent_output,
        "```",
        "",
    ])

    if file_contents:
        lines.append("## Changed File Contents")
        for path, content in file_contents.items():
            truncated = content[:2000] + "..." if len(content) > 2000 else content
            lines.extend([
                f"### File: {path}",
                "```",
                truncated,
                "```",
                "",
            ])
        lines.append("")

    if diff:
        lines.extend([
            "## Diff",
            "```diff",
            diff[:3000] if len(diff) > 3000 else diff,
            "```",
            "",
        ])

    lines.extend([
        "## Effort Configuration",
        f"- Level: {effort_config.get('level', 'thorough')}",
        f"- Min Drafts: {effort_config.get('min_drafts', 2)}",
        f"- Always Verify: {effort_config.get('always_verify', True)}",
        f"- No Shortcuts: {effort_config.get('no_shortcuts', True)}",
        f"- Research Before Code: {effort_config.get('research_before_code', True)}",
        f"- Fail on Single Pass: {effort_config.get('fail_on_single_pass', True)}",
        f"- Fail on Good Enough: {effort_config.get('fail_on_good_enough', True)}",
        "",
    ])

    if verification_commands is not None:
        lines.extend([
            "## Verification Commands",
            f"- Commands provided: {len(verification_commands)}",
            f"- Verification enforcement passed: {verification_passed}",
        ])
        if verification_commands:
            for cmd in verification_commands[:10]:
                lines.append(f"  - `{cmd}`")
        lines.append("")

    if shortcut_issues is not None:
        lines.extend([
            "## Shortcut Detection",
            f"- Issues detected: {shortcut_issues}",
            f"- Phrases found: {shortcut_phrases}",
            "",
        ])

    lines.extend([
        "## Iteration Tracking",
        f"- Draft count: {draft_count}",
        f"- Required minimum: {effort_config.get('min_drafts', 2)}",
        "",
    ])

    if research_passed is not None:
        lines.extend([
            "## Research Enforcement",
            f"- Research passed: {research_passed}",
            "",
        ])

    lines.extend([
        "## Your Evaluation",
        "Based on the above information, determine if the work meets effort standards.",
        "",
        "Look for:",
        "1. Shortcut language (good enough, should work, done., just implement)",
        "2. Missing verification evidence (no test runs, no verification commands)",
        "3. Single-pass completion (claiming done without iteration)",
        "4. Missing research before implementation",
        "5. Vague or placeholder content",
        "",
        "Return your verdict as a JSON object:",
        "{",
        '  "verdict": "done|redo|fail",',
        '  "reasoning": "...",',
        '  "issues": ["issue1", "issue2"],',
        '  "principle_violated": "...",',
        '  "category": "process|verification|shortcut|research",',
        '  "suggestion": "..."',
        "}",
    ])

    return "\n".join(lines)
