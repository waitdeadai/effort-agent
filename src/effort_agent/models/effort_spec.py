"""EffortSpec — parsed representation of an effort.md file."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class ProcessPhilosophy(BaseModel):
    """The process philosophy section of effort.md."""

    text: str = ""
    raw: str = ""


class VerificationRequirements(BaseModel):
    """The verification requirements section."""

    requirements: list[str] = Field(default_factory=list)
    raw: str = ""


class IterationStandards(BaseModel):
    """The iteration standards section."""

    min_drafts: int = 2
    max_single_pass: bool = True  # True = NEVER allowed
    review_cycles: int = 2
    research_before_code: bool = True
    raw: str = ""


class ForbiddenShortcuts(BaseModel):
    """The forbidden shortcuts section."""

    shortcuts: list[str] = Field(default_factory=list)
    raw: str = ""


class EffortLevelSpec(BaseModel):
    """Specification for an effort level."""

    level: str
    min_drafts: int
    always_verify: bool
    no_shortcuts: bool


class EffortSpec(BaseModel):
    """
    Parsed effort.md file structure.

    This is the in-memory representation of an effort.md file
    that guides the EffortAgent's evaluation.

    Attributes:
        project_name: The name of the project.
        process_philosophy: One-paragraph description of how thorough
                           execution should be.
        verification_requirements: List of verification requirement strings.
        iteration_standards: Iteration/draft requirements.
        forbidden_shortcuts: List of explicitly forbidden shortcut phrases.
        effort_levels: Named effort levels with their parameters.
        raw: The original markdown text (for reference/debugging).
        source_path: Path to the effort.md file if loaded from disk.
    """

    project_name: str = "unknown"
    process_philosophy: Optional[ProcessPhilosophy] = None
    verification_requirements: VerificationRequirements = Field(
        default_factory=VerificationRequirements
    )
    iteration_standards: IterationStandards = Field(
        default_factory=IterationStandards
    )
    forbidden_shortcuts: ForbiddenShortcuts = Field(
        default_factory=ForbiddenShortcuts
    )
    effort_levels: dict[str, EffortLevelSpec] = Field(default_factory=dict)
    raw: str = ""
    source_path: Optional[str] = None

    @classmethod
    def from_markdown(cls, text: str, source_path: Optional[str] = None) -> "EffortSpec":
        """
        Parse an effort.md markdown file into an EffortSpec.

        Args:
            text: The raw markdown content of effort.md.
            source_path: Optional path to the source file.

        Returns:
            An EffortSpec instance.
        """
        import re

        spec = cls(raw=text, source_path=source_path)

        # Extract project name from first H1
        h1_match = re.search(r"^#\s+Effort\s*[-—]\s*(.+)$", text, re.MULTILINE)
        if h1_match:
            spec.project_name = h1_match.group(1).strip()

        # Extract Process Philosophy (first ## 1. block)
        phil_match = re.search(
            r"##\s*1\.\s*Process\s+Philosophy\s*\n+(.+?)(?=\n##|\Z)",
            text,
            re.DOTALL | re.IGNORECASE,
        )
        if phil_match:
            raw_phil = phil_match.group(1).strip()
            spec.process_philosophy = ProcessPhilosophy(
                text=raw_phil,
                raw=raw_phil,
            )

        # Extract Verification Requirements
        verif_match = re.search(
            r"##\s*2\.\s*Verification\s+Requirements\s*\n+(.+?)(?=\n##|\Z)",
            text,
            re.DOTALL | re.IGNORECASE,
        )
        if verif_match:
            raw_verif = verif_match.group(1).strip()
            requirements = [
                line.strip().lstrip("-* ")
                for line in raw_verif.split("\n")
                if line.strip().startswith(("-" , "*"))
            ]
            spec.verification_requirements = VerificationRequirements(
                requirements=requirements,
                raw=raw_verif,
            )

        # Extract Iteration Standards
        iter_match = re.search(
            r"##\s*3\.\s*Iteration\s+Standards\s*\n+(.+?)(?=\n##|\Z)",
            text,
            re.DOTALL | re.IGNORECASE,
        )
        if iter_match:
            raw_iter = iter_match.group(1).strip()
            min_drafts = 2
            max_single_pass = True
            review_cycles = 2
            research_before_code = True

            dm = re.search(r"Minimum\s+drafts?\s+per\s+task:\s*(\d+)", raw_iter, re.IGNORECASE)
            if dm:
                min_drafts = int(dm.group(1))

            if re.search(r"Maximum\s+single[- ]pass\s+completion:\s*NEVER", raw_iter, re.IGNORECASE):
                max_single_pass = True
            elif re.search(r"Maximum\s+single[- ]pass\s+completion:\s*(\d+)", raw_iter, re.IGNORECASE):
                max_single_pass = False

            rc = re.search(r"Review\s+cycles?\s+before\s+accept:\s*(\d+)", raw_iter, re.IGNORECASE)
            if rc:
                review_cycles = int(rc.group(1))

            if re.search(r"Research\s+MUST\s+precede\s+implementation", raw_iter, re.IGNORECASE):
                research_before_code = True

            spec.iteration_standards = IterationStandards(
                min_drafts=min_drafts,
                max_single_pass=max_single_pass,
                review_cycles=review_cycles,
                research_before_code=research_before_code,
                raw=raw_iter,
            )

        # Extract Forbidden Shortcuts
        shortcuts_match = re.search(
            r"##\s*4\.\s*Forbidden\s+Shortcuts\s*\n+(.+?)(?=\n##|\Z)",
            text,
            re.DOTALL | re.IGNORECASE,
        )
        if shortcuts_match:
            raw_shortcuts = shortcuts_match.group(1).strip()
            shortcuts = [
                line.strip().lstrip("-* ")
                for line in raw_shortcuts.split("\n")
                if line.strip().startswith(("-" , "*"))
            ]
            spec.forbidden_shortcuts = ForbiddenShortcuts(
                shortcuts=shortcuts,
                raw=raw_shortcuts,
            )

        # Extract Effort Levels table
        levels: dict[str, EffortLevelSpec] = {}
        table_match = re.search(
            r"##\s*5\.\s*Effort\s+Levels\s*\n+(.+)",
            text,
            re.DOTALL | re.IGNORECASE,
        )
        if table_match:
            table_text = table_match.group(1)
            rows = re.findall(r"\|\s*(\w+)\s*\|\s*(\d+)\s*\|\s*(true|false)\s*\|\s*(true|false)\s*\|", table_text, re.IGNORECASE)
            for level, drafts, verify, no_shortcut in rows:
                levels[level.lower()] = EffortLevelSpec(
                    level=level.lower(),
                    min_drafts=int(drafts),
                    always_verify=verify.lower() == "true",
                    no_shortcuts=no_shortcut.lower() == "true",
                )
        else:
            # Default effort levels
            levels = {
                "efficient": EffortLevelSpec(level="efficient", min_drafts=1, always_verify=False, no_shortcuts=False),
                "thorough": EffortLevelSpec(level="thorough", min_drafts=2, always_verify=True, no_shortcuts=True),
                "exhaustive": EffortLevelSpec(level="exhaustive", min_drafts=3, always_verify=True, no_shortcuts=True),
                "perfectionist": EffortLevelSpec(level="perfectionist", min_drafts=4, always_verify=True, no_shortcuts=True),
            }

        spec.effort_levels = levels
        return spec

    @classmethod
    def from_path(cls, path: str | Path) -> "EffortSpec":
        """
        Load and parse an effort.md file from disk.

        Args:
            path: Path to the effort.md file.

        Returns:
            An EffortSpec instance.
        """
        p = Path(path)
        text = p.read_text(encoding="utf-8")
        return cls.from_markdown(text, source_path=str(p))

    def get_level(self, level: str) -> EffortLevelSpec:
        """
        Get the specification for a named effort level.

        Args:
            level: The level name (efficient, thorough, exhaustive, perfectionist).

        Returns:
            The EffortLevelSpec for that level.
        """
        return self.effort_levels.get(level.lower(), self.effort_levels.get("thorough"))

    def get_principle(self) -> str:
        """
        Get the process philosophy as a single principle string.

        Returns:
            The process philosophy text, or a default.
        """
        if self.process_philosophy:
            return self.process_philosophy.text
        return (
            "No shortcuts allowed. Every implementation requires research, "
            "drafting, verification, and iteration. Speed is secondary to "
            "correctness and completeness."
        )
