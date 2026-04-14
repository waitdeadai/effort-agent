"""VerificationEnforcer — enforces that verification evidence is present."""

from typing import Optional, Protocol

from effort_agent.core.effort_config import EffortConfig


class AgentResultLike(Protocol):
    """
    Protocol for agent result objects.
    EffortAgent evaluates any object that has these attributes.
    """

    verification_commands: list[str]
    """List of verification commands that were run."""

    tests_run: Optional[bool] = None
    """Whether tests were actually run."""

    tests_passed: Optional[bool] = None
    """Whether tests passed if run."""

    manual_verification_done: Optional[bool] = None
    """Whether manual verification was performed."""


class VerificationEnforcer:
    """
    Enforces verification requirements for task completion.

    When always_verify=True in config, the agent must provide
    non-empty verification_commands in its result. This ensures
    that "I ran the tests" actually happened rather than being
    assumed.
    """

    def __init__(self, config: Optional[EffortConfig] = None):
        """
        Initialize the VerificationEnforcer.

        Args:
            config: EffortConfig controlling verification requirements.
        """
        self.config = config or EffortConfig()

    def evaluate(
        self,
        agent_result: AgentResultLike,
        file_contents: Optional[dict[str, str]] = None,
    ) -> tuple[bool, str]:
        """
        Evaluate whether verification requirements were met.

        Args:
            agent_result: The agent's result object containing
                         verification_commands and related fields.
            file_contents: Optional dict of file paths to content for
                          additional verification evidence scanning.

        Returns:
            A tuple of (passed, reasoning).
            passed: True if verification requirements are satisfied.
            reasoning: Human-readable explanation.
        """
        if not self.config.is_verification_required():
            return True, "Verification not required by config."

        verification_commands = getattr(agent_result, "verification_commands", [])

        # Check 1: Non-empty verification_commands list
        if not verification_commands:
            return False, (
                "No verification_commands provided. "
                "Verification is required but no evidence of verification was found. "
                "Include the actual commands run (e.g., pytest, curl, manual test) "
                "in the verification_commands field."
            )

        # Check 2: At least one substantive command
        substantive = self._is_substantive(verification_commands)
        if not substantive:
            return False, (
                f"verification_commands present but appears to contain "
                f"placeholder or generic commands: {verification_commands}. "
                f"Provide the actual commands that were executed."
            )

        # Check 3: tests_run flag if present
        tests_run = getattr(agent_result, "tests_run", None)
        if tests_run is False:
            return False, (
                "tests_run=False despite verification_commands being provided. "
                "Tests were listed but apparently not actually executed."
            )

        # Check 4: If tests_passed is explicitly False, fail
        tests_passed = getattr(agent_result, "tests_passed", None)
        if tests_passed is False:
            return False, (
                "tests_passed=False. Verification failed — address test failures "
                "before claiming completion."
            )

        # Check 5: Manual verification flag
        manual_done = getattr(agent_result, "manual_verification_done", None)
        if manual_done is False:
            return False, (
                "manual_verification_done=False. Manual verification was "
                "expected but not performed."
            )

        # Check 6: Scan file contents for verification evidence
        if file_contents:
            evidence = self._scan_for_evidence(file_contents)
            if not evidence:
                return False, (
                    "No verification evidence found in file contents. "
                    "Expected to see test output, command results, or "
                    "verification artifacts in the changed files."
                )

        return True, (
            f"Verification requirements met. "
            f"{len(verification_commands)} verification command(s) provided."
        )

    def _is_substantive(self, commands: list[str]) -> bool:
        """
        Determine if a list of commands appears substantive.

        Args:
            commands: List of command strings.

        Returns:
            True if at least one command appears to be a real
            verification command (not just a placeholder).
        """
        placeholder_keywords = {
            "todo",
            "fixme",
            "example",
            "your command here",
            "command here",
            "replace this",
            "[command]",
            "<command>",
        }

        for cmd in commands:
            cmd_lower = cmd.lower().strip()
            # Must have some non-placeholder content
            if not cmd_lower:
                continue
            # Skip pure placeholders
            if cmd_lower in placeholder_keywords:
                continue
            # Must contain some executable-like pattern
            if any(kw in cmd_lower for kw in ["pytest", "python", "curl", "test", "run", "execute", "check", "verify", "node", "npm", "cargo"]):
                return True
            # Must be longer than 3 chars to be meaningful
            if len(cmd_lower) > 3:
                return True

        return False

    def _scan_for_evidence(self, file_contents: dict[str, str]) -> bool:
        """
        Scan file contents for verification-related evidence.

        Looks for common patterns that indicate verification was performed:
        - Test output / test files
        - Build artifacts
        - Logs
        - Verified OK / PASSED markers

        Args:
            file_contents: Dict mapping file paths to content.

        Returns:
            True if any evidence of verification is found.
        """
        evidence_patterns = [
            r"passed",
            r"failed",
            r"error",
            r"ok",
            r"verified",
            r"tested",
            r"assert",
            r"expect",
            r"coverage",
            r"lint",
            r"flake8",
            r"ruff",
            r"black",
            r"mypy",
        ]

        for file_path, content in file_contents.items():
            # Skip binary/large files
            if len(content) > 500_000:
                continue

            for pattern in evidence_patterns:
                import re

                if re.search(pattern, content, re.IGNORECASE):
                    return True

        return False
