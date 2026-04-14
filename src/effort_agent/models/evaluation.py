"""EvaluationResult — structured output from evaluator components."""

from dataclasses import dataclass, field
from typing import Optional

from effort_agent.core.verdict import EffortVerdict


@dataclass
class EvaluationResult:
    """
    The output of a single evaluator component.

    Each evaluator (shortcut_detector, verification_enforcer, etc.)
    returns an EvaluationResult that is aggregated into an EffortResult.

    Attributes:
        evaluator_name: Which evaluator produced this result.
        passed: Whether this evaluator's check passed.
        verdict: The suggested verdict from this evaluator alone.
        reasoning: Explanation of this evaluator's decision.
        issues: Issue names detected by this evaluator.
        shortcut_phrases: Specific phrases matched (for shortcut detector).
        evidence: Key evidence that contributed to the decision.
        severity: How severe the issues are ("error", "warning", "info").
    """

    evaluator_name: str
    passed: bool
    verdict: EffortVerdict = EffortVerdict.DONE
    reasoning: str = ""
    issues: list[str] = field(default_factory=list)
    shortcut_phrases: list[str] = field(default_factory=list)
    evidence: dict = field(default_factory=dict)
    severity: str = "info"  # "error" | "warning" | "info"

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "evaluator_name": self.evaluator_name,
            "passed": self.passed,
            "verdict": self.verdict.value if isinstance(self.verdict, EffortVerdict) else self.verdict,
            "reasoning": self.reasoning,
            "issues": self.issues,
            "shortcut_phrases": self.shortcut_phrases,
            "evidence": self.evidence,
            "severity": self.severity,
        }

    @classmethod
    def pass_result(
        cls,
        evaluator_name: str,
        reasoning: str,
        evidence: Optional[dict] = None,
    ) -> "EvaluationResult":
        """Create a passing result."""
        return cls(
            evaluator_name=evaluator_name,
            passed=True,
            verdict=EffortVerdict.DONE,
            reasoning=reasoning,
            evidence=evidence or {},
            severity="info",
        )

    @classmethod
    def fail_result(
        cls,
        evaluator_name: str,
        reasoning: str,
        verdict: EffortVerdict,
        issues: list[str],
        evidence: Optional[dict] = None,
        severity: str = "error",
        shortcut_phrases: Optional[list[str]] = None,
    ) -> "EvaluationResult":
        """Create a failing result."""
        ev = evidence or {}
        if shortcut_phrases:
            ev["shortcut_phrases"] = shortcut_phrases
        return cls(
            evaluator_name=evaluator_name,
            passed=False,
            verdict=verdict,
            reasoning=reasoning,
            issues=issues,
            shortcut_phrases=shortcut_phrases or [],
            evidence=ev,
            severity=severity,
        )

    @classmethod
    def warning_result(
        cls,
        evaluator_name: str,
        reasoning: str,
        issues: Optional[list[str]] = None,
        evidence: Optional[dict] = None,
    ) -> "EvaluationResult":
        """Create a warning result (passed but with caveats)."""
        return cls(
            evaluator_name=evaluator_name,
            passed=True,
            verdict=EffortVerdict.DONE,
            reasoning=reasoning,
            issues=issues or [],
            evidence=evidence or {},
            severity="warning",
        )


@dataclass
class AggregateEvaluation:
    """
    Aggregated results from all evaluators.

    This is the output of EffortAgent.evaluate() before converting
    to an EffortResult.

    Attributes:
        results: List of individual EvaluationResults.
        overall_passed: Whether all evaluators passed.
        overall_verdict: The aggregated verdict.
        critical_issues: Issues that are severity=error.
        warnings: Issues that are severity=warning.
    """

    results: list[EvaluationResult] = field(default_factory=list)

    @property
    def overall_passed(self) -> bool:
        """Return True if all evaluators passed."""
        return all(r.passed for r in self.results)

    @property
    def overall_verdict(self) -> EffortVerdict:
        """
        Return the most severe verdict across all evaluators.

        FAIL > REDO > DONE
        """
        verdict_priority = {
            EffortVerdict.FAIL: 3,
            EffortVerdict.REDO: 2,
            EffortVerdict.DONE: 1,
        }

        max_verdict = EffortVerdict.DONE
        max_priority = 0

        for result in self.results:
            p = verdict_priority.get(result.verdict, 0)
            if p > max_priority:
                max_priority = p
                max_verdict = result.verdict

        return max_verdict

    @property
    def critical_issues(self) -> list[str]:
        """Return all issues with severity=error."""
        issues = []
        for r in self.results:
            if r.severity == "error":
                issues.extend(r.issues)
        return issues

    @property
    def warnings(self) -> list[str]:
        """Return all issues with severity=warning."""
        issues = []
        for r in self.results:
            if r.severity == "warning":
                issues.extend(r.issues)
        return issues

    def add(self, result: EvaluationResult) -> None:
        """Add an evaluator result."""
        self.results.append(result)

    def get(self, evaluator_name: str) -> Optional[EvaluationResult]:
        """Get the result for a specific evaluator."""
        for r in self.results:
            if r.evaluator_name == evaluator_name:
                return r
        return None

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "overall_passed": self.overall_passed,
            "overall_verdict": self.overall_verdict.value if isinstance(self.overall_verdict, EffortVerdict) else self.overall_verdict,
            "critical_issues": self.critical_issues,
            "warnings": self.warnings,
            "evaluators": [r.to_dict() for r in self.results],
        }
