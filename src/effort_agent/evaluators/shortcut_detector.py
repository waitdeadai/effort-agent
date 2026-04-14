"""ShortcutDetector — regex pattern detector for common shortcut phrases."""

import re
from typing import Optional

from effort_agent.core.effort_config import EffortConfig


# Built-in shortcut pattern categories.
# Each entry: (name, regex_list, severity)
# severity: "redo" = triggers REDO, "fail" = triggers FAIL
SHORTCUT_PATTERNS: dict[str, tuple[str, list[str], str]] = {
    "skipped_verification": (
        "skipped_verification",
        [
            r"no need to run tests?",
            r"skip(?:ping)? verification",
            r"won't run tests?",
            r"don't need to test",
            r"test later",
            r"skip tests? for now",
            r"we can test (?:it )?later",
            r"verification can wait",
            r"don't have time to test",
            r"tests? are optional here",
            r"won't bother testing",
        ],
        "redo",
    ),
    "good_enough_language": (
        "good_enough_language",
        [
            r"good enough",
            r"should work",
            r"looks good(?:\s+to me)?",
            r"sufficient(?: enough)?",
            r"that'll do",
            r"close enough",
            r"probably works?",
            r"might as well",
            r"ship it",
            r"push it out",
            r"move on",
            r"we can iterate later",
        ],
        "redo",
    ),
    "single_pass": (
        "single_pass",
        [
            r"^(?:done|complete|finished|all\s+set)[\.\!]?\s*$",
            r"\b(?:done|complete|finished)\s*\.$",
            r"\ball\s+done\b",
            r"\btask\s+is\s+done\b",
            r"\bthat's\s+it\b",
            r"\bwrapping\s+up\b",
            r"\bready\s+to\s+go\b",
        ],
        "redo",
    ),
    "vague_copy": (
        "vague_copy",
        [
            r"we help you",
            r"transform your",
            r"seamless(?:ly)?",
            r"cutting[- ]?edge",
            r"leveraging",
            r"synergy",
            r"paradigm shift",
            r"best[- ]in[- ]class",
            r"world[- ]class",
            r"next[- ]gen(?:eration)?",
            r"revolutionize",
            r"disrupt(?:ive)?",
            r"empower(?:ing)?",
        ],
        "redo",
    ),
    "assumptions": (
        "assumptions",
        [
            r"assume it will work",
            r"assuming correctness",
            r"assumed to be correct",
            r"should be fine",
            r"likely correct",
            r"probably correct",
            r"this should work",
            r"trust me on this",
            r"it should just work",
            r"in theory",
            r"based on assumption",
        ],
        "redo",
    ),
    "placeholder_code": (
        "placeholder_code",
        [
            r"// TODO",
            r"# TODO",
            r"TODO:",
            r"TBD",
            r"placeholder",
            r"stub(?:bed)? out",
            r"dummy data",
            r"fake(?:d)? data",
            r"hardcoded for now",
            r"mock(?:ed)? for now",
            r"will implement later",
            r"simplified for demo",
        ],
        "redo",
    ),
}


class ShortcutDetector:
    """
    Detects common shortcut phrases in agent output.

    The detector scans text for patterns across several categories:
    - skipped_verification: Evidence of skipping tests/verification
    - good_enough_language: "Good enough" / "Should work" language
    - single_pass: Premature completion language
    - vague_copy: Corporate buzzword / vague marketing copy
    - assumptions: Unverified assumptions
    - placeholder_code: TODO/FIXME/placeholder markers
    """

    def __init__(self, config: Optional[EffortConfig] = None):
        """
        Initialize the ShortcutDetector.

        Args:
            config: EffortConfig. If provided, custom shortcuts_blocked
                   from config are added to the scan.
        """
        self.config = config or EffortConfig()
        self._compiled: dict[str, re.Pattern] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Pre-compile all regex patterns for performance."""
        self._compiled.clear()

        for name, (_, patterns, _) in SHORTCUT_PATTERNS.items():
            for pattern in patterns:
                try:
                    self._compiled[f"{name}:{pattern}"] = re.compile(
                        pattern, re.IGNORECASE | re.MULTILINE
                    )
                except re.error:
                    # Fall back to literal match if regex is invalid
                    escaped = re.escape(pattern)
                    self._compiled[f"{name}:{pattern}"] = re.compile(
                        escaped, re.IGNORECASE | re.MULTILINE
                    )

        # Add custom shortcuts from config
        for pattern in self.config.shortcuts_blocked:
            try:
                self._compiled[f"custom:{pattern}"] = re.compile(
                    pattern, re.IGNORECASE | re.MULTILINE
                )
            except re.error:
                escaped = re.escape(pattern)
                self._compiled[f"custom:{pattern}"] = re.compile(
                    escaped, re.IGNORECASE | re.MULTILINE
                )

    def detect(
        self,
        text: str,
        fail_on_single_pass: bool = True,
        fail_on_good_enough: bool = True,
    ) -> tuple[list[str], list[str]]:
        """
        Scan text for shortcut phrases.

        Args:
            text: The output text to scan.
            fail_on_single_pass: Whether single-pass phrases trigger REDO.
            fail_on_good_enough: Whether good-enough language triggers REDO.

        Returns:
            A tuple of (issues, shortcut_phrases_found).
            issues: List of issue type names detected.
            shortcut_phrases_found: List of specific phrases matched.
        """
        if not text:
            return [], []

        issues: list[str] = []
        shortcut_phrases_found: list[str] = []

        for key, pattern in self._compiled.items():
            match = pattern.search(text)
            if match:
                category = key.split(":", 1)[0]

                # Filter based on config
                if category == "single_pass" and not fail_on_single_pass:
                    continue
                if category == "good_enough_language" and not fail_on_good_enough:
                    continue

                issue_name, _, severity = SHORTCUT_PATTERNS.get(
                    category, (category, [], "redo")
                )

                issues.append(issue_name)
                shortcut_phrases_found.append(match.group(0))

        return issues, shortcut_phrases_found

    def detect_in_files(
        self,
        file_contents: dict[str, str],
        fail_on_single_pass: bool = True,
        fail_on_good_enough: bool = True,
    ) -> tuple[list[str], list[str]]:
        """
        Scan multiple files for shortcut phrases.

        Args:
            file_contents: A dict mapping file paths to their contents.
            fail_on_single_pass: Whether single-pass phrases trigger REDO.
            fail_on_good_enough: Whether good-enough language triggers REDO.

        Returns:
            A tuple of (issues, shortcut_phrases_found), deduplicated across files.
        """
        all_issues: list[str] = []
        all_phrases: list[str] = []

        for file_path, content in file_contents.items():
            issues, phrases = self.detect(
                content,
                fail_on_single_pass=fail_on_single_pass,
                fail_on_good_enough=fail_on_good_enough,
            )
            all_issues.extend(issues)
            all_phrases.extend(phrases)

        return list(set(all_issues)), list(set(all_phrases))

    @classmethod
    def category_description(cls, category: str) -> str:
        """Return a human-readable description for a shortcut category."""
        descriptions = {
            "skipped_verification": "Evidence of skipping tests or verification steps.",
            "good_enough_language": "Use of 'good enough' / 'should work' language.",
            "single_pass": "Premature completion — only one pass detected.",
            "vague_copy": "Vague corporate copy / buzzwords without specifics.",
            "assumptions": "Unverified assumptions presented as facts.",
            "placeholder_code": "TODO/FIXME/placeholder markers left in code.",
        }
        return descriptions.get(category, f"Shortcut category: {category}")
