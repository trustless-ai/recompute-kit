"""Regression: requires_live exclusions age visibly (pipavlo82 on trustless-ai/recompute-kit#52).
Past review_after an exclusion no longer excuses its suite; undated exclusions are reported."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_conformance as runner  # noqa: E402


class LiveExclusionLifecycleTests(unittest.TestCase):
    def test_future_review_after_still_excuses(self):
        self.assertFalse(runner._live_exclusion_overdue({"review_after": "2026-10-24"}, today="2026-09-24"))

    def test_past_review_after_no_longer_excuses(self):
        self.assertTrue(runner._live_exclusion_overdue({"review_after": "2026-10-24"}, today="2026-10-25"))

    def test_review_after_day_itself_still_excuses(self):
        self.assertFalse(runner._live_exclusion_overdue({"review_after": "2026-10-24"}, today="2026-10-24"))

    def test_undated_entry_is_not_overdue_but_is_reported_undated(self):
        self.assertFalse(runner._live_exclusion_overdue({}, today="2030-01-01"))

    def test_current_manifest_entries_are_dated(self):
        undated, overdue = runner.live_exclusion_lifecycle(today="2026-09-24")
        self.assertEqual(undated, [])
        self.assertEqual(overdue, [])


class OverdueIsDeterministicTests(unittest.TestCase):
    def test_expired_exclusion_whose_suite_passes_is_still_unverifiable(self):
        # the regression pipavlo82 asked for on #55: expired + the (mocked) live suite PASSES -> still exit 2
        rs = [runner.Result("ens-write-v0", True, "", "all vectors reproduced")]
        runner.apply_overdue(rs, ["ens-write-v0"])
        self.assertFalse(rs[0].ok)
        self.assertEqual(rs[0].kind, "NOT COVERED")
        self.assertIn("PASS", rs[0].detail)
        self.assertEqual(runner.exit_code_for_failures(rs), 2)

    def test_multi_check_sub_results_are_covered_and_others_untouched(self):
        rs = [runner.Result("x-live/a", True, "", ""), runner.Result("x-live/b", False, "SUITE", "bad"), runner.Result("other", True, "", "")]
        runner.apply_overdue(rs, ["x-live"])
        self.assertEqual([r.kind for r in rs[:2]], ["NOT COVERED", "NOT COVERED"])
        self.assertTrue(rs[2].ok)


if __name__ == "__main__":
    unittest.main()
