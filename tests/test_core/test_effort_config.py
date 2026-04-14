"""tests/test_core/test_effort_config.py — EffortConfig tests."""
from __future__ import annotations

import pytest
from effort_agent import EffortConfig

class TestEffortConfigDefaults:
    def test_defaults(self):
        config = EffortConfig()
        assert config.enabled is False
        assert config.level is None
        assert config.min_drafts == 2
        assert config.always_verify is True
        assert config.no_shortcuts is True

class TestEffortConfigPresets:
    def test_efficient_preset(self):
        config = EffortConfig(enabled=True, level="efficient")
        assert config.min_drafts == 1
        assert config.always_verify is False
        assert config.no_shortcuts is False

    def test_thorough_preset(self):
        config = EffortConfig(enabled=True, level="thorough")
        assert config.min_drafts == 2
        assert config.always_verify is True
        assert config.no_shortcuts is True

    def test_exhaustive_preset(self):
        config = EffortConfig(enabled=True, level="exhaustive")
        assert config.min_drafts == 3
        assert config.always_verify is True
        assert config.no_shortcuts is True

    def test_perfectionist_preset(self):
        config = EffortConfig(enabled=True, level="perfectionist")
        assert config.min_drafts == 4
        assert config.always_verify is True
        assert config.no_shortcuts is True

    def test_unknown_level_ignored(self):
        config = EffortConfig(enabled=True, level="unknown")
        assert config.min_drafts == 2  # unchanged

class TestEffortConfigHelpers:
    def test_is_verification_required_disabled(self):
        config = EffortConfig(enabled=False, always_verify=True)
        assert config.is_verification_required() is False

    def test_is_verification_required_enabled(self):
        config = EffortConfig(enabled=True, always_verify=True)
        assert config.is_verification_required() is True


class TestEffortConfigIsShortcutBlocked:
    """EffortConfig.is_shortcut_blocked() — the method was fixed to extract patterns from tuples."""

    def test_is_shortcut_blocked_literal(self):
        """Literal shortcut phrases from built-in SHORTCUT_PATTERNS are blocked."""
        config = EffortConfig(enabled=True, no_shortcuts=True)
        # "no need to run tests?" is a built-in pattern
        assert config.is_shortcut_blocked("I did not run the tests, no need to run tests?") is True
        assert config.is_shortcut_blocked("This is fine, all tests pass") is False

    def test_is_shortcut_blocked_custom_literal(self):
        """Custom literal phrases added via shortcuts_blocked are blocked."""
        config = EffortConfig(enabled=True, shortcuts_blocked=["magic wand", "done and done"])
        assert config.is_shortcut_blocked("I waved my magic wand and it works") is True
        assert config.is_shortcut_blocked("done and done, ship it") is True
        assert config.is_shortcut_blocked("I tested thoroughly") is False

    def test_is_shortcut_blocked_custom_regex(self):
        """Custom regex patterns in shortcuts_blocked are evaluated as regex."""
        config = EffortConfig(enabled=True, shortcuts_blocked=[r"ship\s*it", r"wraps?\s*up"])
        assert config.is_shortcut_blocked("Let's ship it now") is True
        assert config.is_shortcut_blocked("wraps up the task") is True
        assert config.is_shortcut_blocked("shipping container") is False  # "ship" alone doesn't match r"ship\s*it"

    def test_is_shortcut_blocked_invalid_regex_falls_back_to_literal(self):
        """Invalid regex in shortcuts_blocked falls back to literal substring match (phrase in pattern)."""
        config = EffortConfig(enabled=True, shortcuts_blocked=["(invalid regex"])
        # Falls back: phrase.lower() in pattern.lower() — phrase must be substring OF pattern
        assert config.is_shortcut_blocked("invalid regex") is True  # phrase is substring of pattern
        assert config.is_shortcut_blocked("something else") is False

    def test_is_shortcut_blocked_case_insensitive(self):
        """Matching is case-insensitive for both literal and pattern modes."""
        config = EffortConfig(enabled=True, shortcuts_blocked=["SHIP IT", r"dOnE\??"])
        assert config.is_shortcut_blocked("ship it now") is True
        assert config.is_shortcut_blocked("DONE??") is True
        assert config.is_shortcut_blocked("done??") is True

    def test_is_shortcut_blocked_disabled_config(self):
        """Method returns False when no_shortcuts=False (though it still evaluates patterns)."""
        config = EffortConfig(enabled=True, no_shortcuts=False)
        # When no_shortcuts=False the method still checks patterns but does not enforce;
        # is_shortcut_blocked itself is a check method, so it returns True on match
        # regardless of no_shortcuts setting.
        assert config.is_shortcut_blocked("no need to run tests?") is True
