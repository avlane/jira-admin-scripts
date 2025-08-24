import unittest

from jiraadmin.actions import run_each
from jiraadmin.client import JiraError


class RunEachTests(unittest.TestCase):
    def test_dry_run_never_calls_perform(self):
        called = []
        rows = run_each(["a", "b"], called.append, planned="would do it")
        self.assertEqual(called, [])
        self.assertEqual(rows, [{"id": "a", "status": "planned", "detail": "would do it"},
                                {"id": "b", "status": "planned", "detail": "would do it"}])

    def test_apply_continues_after_a_failure(self):
        def perform(item):
            if item == "b":
                raise JiraError("nope", 400)

        rows = run_each(["a", "b", "c"], perform, apply=True, key="key", done="archived")
        self.assertEqual([(r["key"], r["status"]) for r in rows], [("a", "archived"), ("b", "failed"), ("c", "archived")])
        self.assertEqual(rows[1]["detail"], "nope")

    def test_other_exceptions_propagate(self):
        with self.assertRaises(ZeroDivisionError):
            run_each(["a"], lambda item: 1 / 0, apply=True)


if __name__ == "__main__":
    unittest.main()
