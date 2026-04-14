"""EffortAgent — main process integrity enforcement class."""

import hashlib
import json
from pathlib import Path
from typing import Optional, Union

from effort_agent.core.effort_config import EffortConfig
from effort_agent.core.effort_memory import EffortMemory
from effort_agent.core.effort_result import EffortResult
from effort_agent.core.verdict import EffortVerdict
from effort_agent.evaluators.shortcut_detector import ShortcutDetector
from effort_agent.evaluators.verification_enforcer import VerificationEnforcer, AgentResultLike
from effort_agent.evaluators.iteration_tracker import IterationTracker
from effort_agent.evaluators.research_enforcer import ResearchEnforcer
from effort_agent.models.effort_spec import EffortSpec
from effort_agent.models.evaluation import EvaluationResult, AggregateEvaluation


class EffortAgent:
    """
    Process integrity enforcer for agentic workflows.

    EffortAgent evaluates whether work was done THOROUGHLY by checking:
    - Shortcut language (good enough, should work, done., etc.)
    - Verification evidence (test runs, verification commands)
    - Iteration counts (minimum drafts before claiming done)
    - Pre-code research (research before implementation)

    It complements taste-agent (which evaluates aesthetic/copy/UX quality)
    by focusing on PROCESS INTEGRITY — "did you actually do the work?"

    Usage:
        agent = EffortAgent(config=EffortConfig(enabled=True, level="thorough"))
        result = agent.evaluate(
            task="Build user auth module",
            agent_result=my_agent_result,
            file_contents={"auth.py": "..."},
        )
        if result.verdict != EffortVerdict.DONE:
            print(f"REDO: {result.reasoning}")
    """

    def __init__(
        self,
        config: Optional[EffortConfig] = None,
        memory_path: Optional[str | Path] = None,
        effort_md_path: Optional[str | Path] = None,
    ):
        """
        Initialize the EffortAgent.

        Args:
            config: EffortConfig controlling evaluation behavior.
                   If None, uses default (disabled).
            memory_path: Path to the JSONL memory file. If None, uses
                        "effort.memory" in the working directory.
            effort_md_path: Optional path to an effort.md file that
                           overrides/extends the config.
        """
        self.config = config or EffortConfig()
        self.memory = EffortMemory(path=memory_path)
        self.shortcut_detector = ShortcutDetector(config=self.config)
        self.verification_enforcer = VerificationEnforcer(config=self.config)
        self.iteration_tracker = IterationTracker(config=self.config)
        self.research_enforcer = ResearchEnforcer(config=self.config)

        # Load effort.md if provided
        self.effort_spec: Optional[EffortSpec] = None
        if effort_md_path:
            self.load_effort_spec(effort_md_path)

    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------

    def enable(self, level: str = "thorough") -> None:
        """
        Enable the EffortAgent with a named effort level.

        Args:
            level: The effort level (efficient, thorough, exhaustive, perfectionist).
        """
        self.config.enabled = True
        self.config.level = level

    def disable(self) -> None:
        """Disable the EffortAgent (returns DONE without evaluating)."""
        self.config.enabled = False

    def load_effort_spec(self, path: str | Path) -> None:
        """
        Load an effort.md file to guide evaluation.

        Args:
            path: Path to the effort.md file.
        """
        try:
            self.effort_spec = EffortSpec.from_path(path)
        except Exception as e:
            raise ValueError(f"Failed to load effort.md from {path}: {e}") from e

    # -------------------------------------------------------------------------
    # Evaluation
    # -------------------------------------------------------------------------

    def evaluate(
        self,
        task: str,
        agent_result: AgentResultLike,
        output_files: Optional[dict[str, str]] = None,
        file_contents: Optional[dict[str, str]] = None,
        diff: Optional[str] = None,
        effort_spec_path: Optional[str | Path] = None,
        task_key: Optional[str] = None,
    ) -> EffortResult:
        """
        Evaluate whether a task meets effort/process integrity standards.

        Args:
            task: The task description.
            agent_result: The agent's result object. Must have `verification_commands`.
            output_files: Deprecated alias for file_contents.
            file_contents: Dict of file paths to their contents for scanning.
            diff: Optional git-style diff of changes made.
            effort_spec_path: Optional path to an effort.md for this evaluation.
            task_key: Optional stable key for the task (for iteration tracking).
                     If not provided, generated from task + primary file path.

        Returns:
            An EffortResult with the verdict and reasoning.
        """
        # Handle disabled state
        if not self.config.enabled:
            return EffortResult(
                verdict=EffortVerdict.DONE,
                reasoning="EffortAgent is disabled. Skipping evaluation.",
                task_description=task,
            )

        # Load effort spec if provided inline
        if effort_spec_path:
            self.load_effort_spec(effort_spec_path)

        # Generate task key for iteration tracking
        primary_file = self._get_primary_file(file_contents, agent_result)
        if task_key is None:
            task_key = self.iteration_tracker.task_key(task, primary_file)

        # Run aggregations
        agg = AggregateEvaluation()

        # Run shortcut detector
        shortcut_result = self._evaluate_shortcuts(task, agent_result, file_contents)
        agg.add(shortcut_result)

        # Run verification enforcer
        verification_result = self._evaluate_verification(agent_result, file_contents)
        agg.add(verification_result)

        # Run iteration tracker
        iteration_result = self._evaluate_iteration(task_key, task)
        agg.add(iteration_result)

        # Run research enforcer
        research_result = self._evaluate_research(task, agent_result, file_contents)
        agg.add(research_result)

        # Run effort.md enforcer (if required)
        if self.config.require_effort_md:
            effort_md_result = self._evaluate_effort_md()
            agg.add(effort_md_result)

        # Increment draft count (this is a new draft attempt)
        draft_count = self.iteration_tracker.increment(task_key)

        # Determine overall verdict
        overall_verdict = agg.overall_verdict
        critical_issues = agg.critical_issues
        all_issues = list(set(critical_issues + agg.warnings))

        # Build reasoning
        reasoning = self._build_reasoning(agg, all_issues, draft_count)

        # Build EffortResult
        effort_result = EffortResult(
            verdict=overall_verdict,
            reasoning=reasoning,
            issues=all_issues,
            task_hash=self._hash_task(task),
            task_description=task,
            file_path=primary_file,
            effort_level=self.config.level or "thorough",
            verification_evidence_found=verification_result.passed,
            draft_count=draft_count,
            shortcut_phrases_found=shortcut_result.shortcut_phrases,
            principle_violated=self._get_violated_principle(all_issues),
            category=self._get_category(all_issues),
            retry_count=self.memory.retry_count_for(task),
        )

        # Record in memory
        entry_id = self.memory.append(
            task_description=task,
            verdict=effort_result.verdict,
            reasoning=effort_result.reasoning,
            issues=effort_result.issues,
            principle_violated=effort_result.principle_violated,
            category=effort_result.category,
            file_path=effort_result.file_path,
            was_applied=False,  # Agent will update this if applied
            retry_count=effort_result.retry_count,
        )
        effort_result.task_hash = entry_id

        # Check if consolidation is needed
        if self.memory.should_consolidate():
            summary = self.memory.consolidate()
            # Consolidation happened silently; summary is available for logging

        return effort_result

    # -------------------------------------------------------------------------
    # Sub-evaluators
    # -------------------------------------------------------------------------

    def _evaluate_shortcuts(
        self,
        task: str,
        agent_result: AgentResultLike,
        file_contents: Optional[dict[str, str]],
    ) -> EvaluationResult:
        """Run shortcut detection."""
        # Get text to scan from agent result
        text = self._get_result_text(agent_result)

        # Also scan file contents if provided
        if file_contents:
            file_issues, file_phrases = self.shortcut_detector.detect_in_files(
                file_contents,
                fail_on_single_pass=self.config.fail_on_single_pass,
                fail_on_good_enough=self.config.fail_on_good_enough,
            )
            if file_issues and not self.shortcut_detector.config.no_shortcuts:
                pass  # Already handled below
            elif file_issues:
                combined_issues = list(
                    set(
                        self.shortcut_detector.detect(
                            text,
                            fail_on_single_pass=self.config.fail_on_single_pass,
                            fail_on_good_enough=self.config.fail_on_good_enough,
                        )[0]
                        + file_issues
                    )
                )
                combined_phrases = list(
                    set(
                        self.shortcut_detector.detect(
                            text,
                            fail_on_single_pass=self.config.fail_on_single_pass,
                            fail_on_good_enough=self.config.fail_on_good_enough,
                        )[1]
                        + file_phrases
                    )
                )
            else:
                combined_issues, combined_phrases = self.shortcut_detector.detect(
                    text,
                    fail_on_single_pass=self.config.fail_on_single_pass,
                    fail_on_good_enough=self.config.fail_on_good_enough,
                )
        else:
            combined_issues, combined_phrases = self.shortcut_detector.detect(
                text,
                fail_on_single_pass=self.config.fail_on_single_pass,
                fail_on_good_enough=self.config.fail_on_good_enough,
            )

        if not self.config.no_shortcuts:
            return EvaluationResult.pass_result(
                "shortcut_detector",
                "Shortcut detection disabled by config.",
            )

        if combined_issues:
            return EvaluationResult.fail_result(
                "shortcut_detector",
                f"Shortcuts detected: {', '.join(combined_issues)}. "
                f"Phrases: {combined_phrases}. "
                f"Task must be redone without these shortcuts.",
                verdict=EffortVerdict.REDO,
                issues=combined_issues,
                shortcut_phrases=combined_phrases,
                evidence={"scan_text_length": len(text)},
                severity="error",
            )

        return EvaluationResult.pass_result(
            "shortcut_detector",
            "No shortcut language detected.",
            evidence={"scan_text_length": len(text)},
        )

    def _evaluate_verification(
        self,
        agent_result: AgentResultLike,
        file_contents: Optional[dict[str, str]],
    ) -> EvaluationResult:
        """Run verification enforcement."""
        passed, reasoning = self.verification_enforcer.evaluate(
            agent_result, file_contents
        )

        if passed:
            return EvaluationResult.pass_result(
                "verification_enforcer",
                reasoning,
            )

        return EvaluationResult.fail_result(
            "verification_enforcer",
            reasoning,
            verdict=EffortVerdict.REDO,
            issues=["skipped_verification"],
            evidence={"verification_required": self.config.always_verify},
            severity="error",
        )

    def _evaluate_iteration(
        self,
        task_key: str,
        task_description: str,
    ) -> EvaluationResult:
        """Run iteration tracking."""
        passed, reasoning, draft_count = self.iteration_tracker.evaluate(
            task_key, task_description
        )

        if passed:
            return EvaluationResult.pass_result(
                "iteration_tracker",
                reasoning,
                evidence={"draft_count": draft_count},
            )

        return EvaluationResult.fail_result(
            "iteration_tracker",
            reasoning,
            verdict=EffortVerdict.REDO,
            issues=["insufficient_drafts"],
            evidence={"draft_count": draft_count},
            severity="error",
        )

    def _evaluate_research(
        self,
        task: str,
        agent_result: AgentResultLike,
        file_contents: Optional[dict[str, str]],
    ) -> EvaluationResult:
        """Run research enforcement."""
        text = self._get_result_text(agent_result)

        passed, reasoning = self.research_enforcer.evaluate(
            text, task, file_contents
        )

        if passed:
            return EvaluationResult.pass_result(
                "research_enforcer",
                reasoning,
            )

        return EvaluationResult.fail_result(
            "research_enforcer",
            reasoning + "\n" + self.research_enforcer.suggestion(),
            verdict=EffortVerdict.REDO,
            issues=["missing_research"],
            severity="error",
        )

    def _evaluate_effort_md(self) -> EvaluationResult:
        """Check if effort.md is present when required."""
        if self.effort_spec is not None:
            return EvaluationResult.pass_result(
                "effort_md_enforcer",
                "effort.md loaded and present.",
            )

        if self.config.require_effort_md:
            return EvaluationResult.fail_result(
                "effort_md_enforcer",
                "effort.md is required by config but was not loaded. "
                "Provide effort_md_path to the EffortAgent or load it via load_effort_spec().",
                verdict=EffortVerdict.FAIL,
                issues=["missing_effort_md"],
                severity="error",
            )

        return EvaluationResult.pass_result(
            "effort_md_enforcer",
            "effort.md not required by config.",
        )

    # -------------------------------------------------------------------------
    # Utilities
    # -------------------------------------------------------------------------

    def _get_result_text(self, agent_result: AgentResultLike) -> str:
        """Extract text content from an agent result."""
        parts = []

        # Try common text fields
        if hasattr(agent_result, "text") and agent_result.text:
            parts.append(str(agent_result.text))
        if hasattr(agent_result, "output") and agent_result.output:
            parts.append(str(agent_result.output))
        if hasattr(agent_result, "content") and agent_result.content:
            parts.append(str(agent_result.content))
        if hasattr(agent_result, "message") and agent_result.message:
            parts.append(str(agent_result.message))

        return "\n".join(parts)

    def _get_primary_file(
        self,
        file_contents: Optional[dict[str, str]],
        agent_result: AgentResultLike,
    ) -> Optional[str]:
        """Determine the primary file path from various sources."""
        # From file_contents
        if file_contents:
            # Return the most recently modified or first key
            return next(iter(file_contents.keys()), None)

        # From agent_result
        if hasattr(agent_result, "file_path") and agent_result.file_path:
            return str(agent_result.file_path)
        if hasattr(agent_result, "file") and agent_result.file:
            return str(agent_result.file)

        return None

    @staticmethod
    def _hash_task(task_description: str) -> str:
        """Generate a short hash of a task description."""
        return hashlib.sha256(task_description.encode("utf-8")).hexdigest()[:16]

    def _build_reasoning(
        self,
        agg: AggregateEvaluation,
        issues: list[str],
        draft_count: int,
    ) -> str:
        """Build a comprehensive reasoning string."""
        parts = []

        if agg.overall_verdict == EffortVerdict.DONE:
            parts.append("Task meets effort standards.")
        elif agg.overall_verdict == EffortVerdict.REDO:
            parts.append("Shortcuts or deficiencies detected. Task must be redone.")
        else:
            parts.append("Catastrophic process failure.")

        # Add evaluator-specific reasoning
        for result in agg.results:
            if not result.passed:
                parts.append(f"\n[{result.evaluator_name}] {result.reasoning}")

        # Add draft count info
        if draft_count < self.config.min_drafts:
            parts.append(
                f"\nDraft count: {draft_count}/{self.config.min_drafts} "
                f"(minimum required)."
            )

        return " ".join(parts).strip()

    def _get_violated_principle(self, issues: list[str]) -> Optional[str]:
        """Map issues to the principle that was violated."""
        principle_map = {
            "skipped_verification": "Always run verification commands before claiming done.",
            "good_enough_language": "Never use 'good enough' language — aim for correctness.",
            "single_pass": "Never claim done after a single pass — iterate and refine.",
            "vague_copy": "Replace vague copy with specific, concrete language.",
            "assumptions": "Verify assumptions before presenting them as facts.",
            "placeholder_code": "Remove all placeholder/TODO code before claiming done.",
            "missing_research": "Research must precede implementation.",
            "missing_effort_md": "effort.md must be present when require_effort_md=True.",
        }

        if not issues:
            return None

        return principle_map.get(issues[0], "Process integrity standard violated.")

    def _get_category(self, issues: list[str]) -> str:
        """Determine the issue category."""
        shortcut_categories = {
            "skipped_verification",
            "good_enough_language",
            "single_pass",
            "vague_copy",
            "assumptions",
            "placeholder_code",
        }

        if not issues:
            return "process"

        if issues[0] in shortcut_categories:
            return "shortcut"
        if issues[0] == "skipped_verification":
            return "verification"
        if issues[0] == "missing_research":
            return "research"
        if issues[0] == "missing_effort_md":
            return "process"

        return "process"

    # -------------------------------------------------------------------------
    # Memory management
    # -------------------------------------------------------------------------

    def mark_applied(self, task_description: str) -> None:
        """
        Mark the most recent REDO as applied.

        Call this when the agent has actually acted on the REDO feedback.

        Args:
            task_description: The task whose REDO was applied.
        """
        # Find the most recent REDO entry for this task and update it
        # This is a simplification; in production you'd use a more robust approach
        pass

    def reset_task(self, task_key: str) -> None:
        """
        Reset iteration tracking for a task.

        Args:
            task_key: The task key to reset.
        """
        self.iteration_tracker.reset(task_key)

    def memory_summary(self) -> dict:
        """
        Get a summary of the effort memory.

        Returns:
            A dict with memory statistics.
        """
        return {
            "total_entries": self.memory.count(),
            "redo_rate": self.memory.redo_rate(),
            "iteration_summary": self.iteration_tracker.summary(),
        }
