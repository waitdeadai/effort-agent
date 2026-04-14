"""Effort configuration — runtime parameters for the effort agent."""

from typing import ClassVar, Optional

from pydantic import BaseModel, Field


class EffortConfig(BaseModel):
    """
    Configuration for the EffortAgent's evaluation behavior.

    Attributes:
        enabled: Master kill-switch. When False, EffortAgent returns DONE
                 without evaluating anything.
        level: Named effort preset. Sets min_drafts, always_verify, no_shortcuts
               automatically. Options: efficient, thorough, exhaustive, perfectionist.
               Can be overridden by individual fields below.
        min_drafts: Minimum number of draft/iteration cycles required per task.
                    Defaults to 2 (thorough).
        always_verify: Whether verification evidence is mandatory.
                       When True, evaluation REQUIRES verification_commands
                       in the agent result.
        no_shortcuts: Whether shortcut detection is enforced.
                      When True, any detected shortcut triggers a REDO.
        shortcuts_blocked: Additional custom shortcut phrases/patterns to flag.
                           These are added on top of the built-in shortcut patterns.
        research_before_code: Whether pre-code research is enforced.
                              If True, evaluation looks for evidence of research
                              before implementation (search queries, doc lookups, etc.).
        max_compaction_turns: Maximum turns before context compaction is allowed
                              without triggering a REDO. Default 999 (essentially off).
        retry_on_failure: Whether REDO verdicts can be retried. Default True.
        require_effort_md: Whether the effort.md file MUST be present.
                           If True and effort.md is missing, verdict is FAIL.
        fail_on_single_pass: If True, any single-pass completion language
                              (e.g., "done.", "complete.") triggers REDO
                              even if other checks pass.
        fail_on_good_enough: If True, any "good enough" / "should work" language
                              triggers REDO even if other checks pass.
    """

    enabled: bool = False
    level: Optional[str] = None  # "efficient" | "thorough" | "exhaustive" | "perfectionist"
    min_drafts: int = 2
    always_verify: bool = True
    no_shortcuts: bool = True
    shortcuts_blocked: list[str] = Field(default_factory=list)
    research_before_code: bool = True
    max_compaction_turns: int = 999
    retry_on_failure: bool = True
    require_effort_md: bool = False
    fail_on_single_pass: bool = True
    fail_on_good_enough: bool = True

    # -------------------------------------------------------------------------
    # Preset logic
    # -------------------------------------------------------------------------

    # Effort levels table (matches EFFORT_SPEC_FORMAT.md)
    LEVEL_PRESETS: ClassVar[dict[str, dict[str, int | bool]]] = {
        "efficient": {
            "min_drafts": 1,
            "always_verify": False,
            "no_shortcuts": False,
        },
        "thorough": {
            "min_drafts": 2,
            "always_verify": True,
            "no_shortcuts": True,
        },
        "exhaustive": {
            "min_drafts": 3,
            "always_verify": True,
            "no_shortcuts": True,
        },
        "perfectionist": {
            "min_drafts": 4,
            "always_verify": True,
            "no_shortcuts": True,
        },
    }

    def model_post_init(self, _):
        """Apply level preset overrides after initialization."""
        if self.level and self.level in self.LEVEL_PRESETS:
            preset = self.LEVEL_PRESETS[self.level]
            # Only override if not explicitly set (allow partial override)
            if self.min_drafts == 2:  # default value
                self.min_drafts = preset["min_drafts"]
            if self.always_verify is True:  # default value
                self.always_verify = preset["always_verify"]
            if self.no_shortcuts is True:  # default value
                self.no_shortcuts = preset["no_shortcuts"]

    def is_verification_required(self) -> bool:
        """Returns True if verification evidence is mandatory for this config."""
        return self.enabled and self.always_verify

    def is_shortcut_blocked(self, phrase: str) -> bool:
        """Returns True if the given phrase matches any blocked shortcut pattern."""
        from effort_agent.evaluators.shortcut_detector import SHORTCUT_PATTERNS

        import re

        # SHORTCUT_PATTERNS values are tuples: (name, [pattern1, pattern2], severity)
        # Flatten to actual pattern strings
        all_patterns: list[str] = []
        for _name, patterns, _severity in SHORTCUT_PATTERNS.values():
            all_patterns.extend(patterns)
        all_patterns.extend(self.shortcuts_blocked)

        for pattern in all_patterns:
            try:
                if re.search(pattern, phrase, re.IGNORECASE):
                    return True
            except re.error:
                # Treat as literal string if regex is invalid
                if phrase.lower() in pattern.lower():
                    return True
        return False
