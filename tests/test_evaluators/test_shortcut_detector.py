"""tests/test_evaluators/test_shortcut_detector.py — shortcut detector tests."""
from __future__ import annotations

import pytest
from effort_agent.evaluators.shortcut_detector import ShortcutDetector

class TestShortcutDetectorPatterns:
    def setup_method(self):
        self.d = ShortcutDetector()

    def test_good_enough(self):
        issues, _ = self.d.detect("This is good enough.", fail_on_good_enough=True)
        assert "good_enough_language" in issues

    def test_should_work(self):
        issues, _ = self.d.detect("This should work fine.", fail_on_good_enough=True)
        assert "good_enough_language" in issues

    def test_single_pass_done(self):
        issues, _ = self.d.detect("Done.", fail_on_single_pass=True)
        assert "single_pass" in issues

    def test_single_pass_complete(self):
        issues, _ = self.d.detect("Complete.", fail_on_single_pass=True)
        assert "single_pass" in issues

    def test_single_pass_all_set(self):
        issues, _ = self.d.detect("All set.", fail_on_single_pass=True)
        assert "single_pass" in issues

    def test_vague_copy(self):
        issues, _ = self.d.detect("We help you transform your business.")
        assert "vague_copy" in issues

    def test_assumptions(self):
        issues, _ = self.d.detect("Assume it will work correctly.")
        assert "assumptions" in issues

    def test_placeholder_code(self):
        issues, _ = self.d.detect("// TODO: fix later")
        assert "placeholder_code" in issues

    def test_clean_text_passes(self):
        issues, _ = self.d.detect(
            "Implemented JWT authentication with proper error handling and comprehensive tests."
        )
        assert len(issues) == 0

    def test_multiple_issues(self):
        # Use string that triggers both placeholder and good_enough
        issues, _ = self.d.detect("// TODO: fix later. This is good enough.")
        assert "placeholder_code" in issues
        assert "good_enough_language" in issues

class TestShortcutDetectorFiles:
    def test_detect_in_files(self):
        d = ShortcutDetector()
        files = {"auth.py": "// TODO: fix later"}
        issues, phrases = d.detect_in_files(files)
        assert "placeholder_code" in issues

    def test_detect_in_files_clean(self):
        d = ShortcutDetector()
        files = {"auth.py": "def authenticate(user): return True"}
        issues, phrases = d.detect_in_files(files)
        assert len(issues) == 0
