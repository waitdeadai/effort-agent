"""ResearchEnforcer — enforces pre-code research before implementation."""

import re
from typing import Optional

from effort_agent.core.effort_config import EffortConfig


# Patterns that indicate research was performed
RESEARCH_PATTERNS = [
    # Search engine queries
    r"search(?:ing|ed)? for",
    r"googled?",
    r"look(?:ing|ed)? up",
    r"query(?:ing)?",
    r"research(?:ing|ed)?",
    r"investigat(?:ing|ed)?",
    r"explor(?:ing|ed)?",

    # Documentation lookups
    r"read(?:ing)? the (?:docs?|documentation)",
    r"docs? say",
    r"according to (?:the )?(?:docs?|documentation)",
    r"check(?:ing)? (?:the )?(?:docs?|docs\.python|reference)",
    r"looked? at (?:the )?(?:api|spec|docs)",
    r"referring to (?:the )?docs?",

    # Verification of facts
    r"verified? that",
    r"confirm(?:ing|ed)? that",
    r"found? in (?:the )?(?:docs?|source|code)",
    r"confirmed? by",
    r"checked? (?:the )?(?:source|code|docs)",

    # Existing code inspection
    r"look(?:ing|ed)? at existing",
    r"review(?:ing|ed)? (?:the )?(?:code|existing)",
    r"inspected? (?:the )?(?:code|source)",
    r"scan(?:ning)? (?:the )?(?:code|source)",
    r"found? in (?:the )?(?:code|source|file)",

    # Search tool usage
    r"use[d]? (?:search|grep|ripgrep|rg)",
    r"ran (?:a )?search",
    r"found (?:the )?following",
    r"search results?",
    r"search(?:ing)? for",
]

# Patterns that indicate implementation without research
NO_RESEARCH_PATTERNS = [
    r"i'?ll (?:just|go ahead and|now)",
    r"(?:just )?implement(?:ing|ed)? (?:it|the|this|that)",
    r"(?:just )?write (?:the |some )?code",
    r"(?:just )?add (?:this|that|it)",
    r"(?:just )?create (?:a |the )?file",
    r"(?:just )?build (?:it|this|that)",
    r"(?:just )?make (?:it|this|that)",
    r"proceeding (?:directly )?to (?:implementation|coding|writing)",
    r"skip(?:ping)? (?:the )?research",
    r"no research (?:needed|required|necessary)",
    r"research is optional here",
]


class ResearchEnforcer:
    """
    Enforces that research precedes implementation.

    When research_before_code=True in config, the agent must
    show evidence of researching before writing code — searching
    docs, reading existing code, verifying facts, etc.
    """

    def __init__(self, config: Optional[EffortConfig] = None):
        """
        Initialize the ResearchEnforcer.

        Args:
            config: EffortConfig controlling research requirements.
        """
        self.config = config or EffortConfig()
        self._research_patterns = [re.compile(p, re.IGNORECASE) for p in RESEARCH_PATTERNS]
        self._no_research_patterns = [re.compile(p, re.IGNORECASE) for p in NO_RESEARCH_PATTERNS]

    def evaluate(
        self,
        agent_output: str,
        task_description: Optional[str] = None,
        file_contents: Optional[dict[str, str]] = None,
    ) -> tuple[bool, str]:
        """
        Evaluate whether research was performed before implementation.

        Args:
            agent_output: The agent's output text.
            task_description: The task description (for context).
            file_contents: Optional dict of file paths to contents.

        Returns:
            A tuple of (passed, reasoning).
            passed: True if research evidence is found (or not required).
            reasoning: Human-readable explanation.
        """
        if not self.config.research_before_code:
            return True, "Research enforcement disabled by config."

        if not agent_output and not file_contents:
            return False, (
                "No output provided for research evaluation. "
                "Cannot verify pre-code research was performed."
            )

        # Count research evidence in output
        research_evidence = self._find_research_evidence(agent_output)
        no_research_evidence = self._find_no_research_evidence(agent_output)

        # Check file contents for research evidence too
        if file_contents:
            for path, content in file_contents.items():
                research_evidence += self._find_research_evidence(content)
                no_research_evidence += self._find_no_research_evidence(content)

        # Strong negative signal: both no-research and research patterns found
        # means agent claimed to research but did not
        if no_research_evidence > 0 and research_evidence == 0:
            return False, (
                f"No research evidence found before implementation. "
                f"{no_research_evidence} instance(s) of implementation-first language detected "
                f"(e.g., 'just implement', 'proceeding to code'). "
                f"Research must precede implementation. "
                f"Show evidence of searching docs, reading existing code, "
                f"or verifying facts before writing code."
            )

        # Mild positive signal: research patterns found
        if research_evidence > 0 and no_research_evidence == 0:
            return True, (
                f"Research evidence found ({research_evidence} research signal(s)). "
                f"Pre-code research requirement met."
            )

        # No strong signals — be lenient but flag it
        if research_evidence == 0 and no_research_evidence == 0:
            # No explicit research claims, but also no anti-patterns
            # This is ambiguous — pass with a warning
            return True, (
                "No explicit research evidence found in output. "
                "Consider adding search/documentation references to confirm "
                "pre-code research was performed."
            )

        # Mixed signals
        if research_evidence > 0 and no_research_evidence > 0:
            return False, (
                f"Mixed research signals: {research_evidence} research claim(s) "
                f"but {no_research_evidence} implementation-first phrase(s). "
                f"Ensure research genuinely precedes implementation."
            )

        return True, "Research evaluation passed."

    def _find_research_evidence(self, text: str) -> int:
        """Count the number of research-related phrases in text."""
        count = 0
        for pattern in self._research_patterns:
            if pattern.search(text):
                count += 1
        return count

    def _find_no_research_evidence(self, text: str) -> int:
        """Count the number of no-research phrases in text."""
        count = 0
        for pattern in self._no_research_patterns:
            if pattern.search(text):
                count += 1
        return count

    def suggestion(self) -> str:
        """
        Return a suggestion for how to demonstrate research.

        This is shown to the agent when research enforcement fails.
        """
        return (
            "To demonstrate pre-code research:\n"
            "  - Show search queries or documentation lookups\n"
            "  - Reference existing code patterns you inspected\n"
            "  - Quote or link to relevant documentation\n"
            "  - Note any facts you verified before implementing\n"
            "Example: 'After checking the Python docs for dataclasses, I implemented...'"
        )
