import unittest
from datetime import datetime, timezone

from jiraadmin import fields
from jiraadmin.client import JiraClient
from tests.helpers import FakeSession, load

NOW = datetime(2022, 4, 17, 12, 0, tzinfo=timezone.utc)


def make_client(session=None):
    session = session or FakeSession().add("GET", r"/rest/api/3/field$", load("field_list.json"))
    return JiraClient("https://example.atlassian.net", session=session)


class FieldListTests(unittest.TestCase):
    def test_only_custom_fields(self):
        got = fields.custom_fields(make_client())
        self.assertEqual(len(got), 7)
        self.assertTrue(all(f["custom"] for f in got))

    def test_field_type_uses_the_plugin_key_suffix(self):
        by_id = {f["id"]: f for f in fields.custom_fields(make_client())}
        self.assertEqual(fields.field_type(by_id["customfield_10030"]), "select")
        self.assertEqual(fields.field_type(by_id["customfield_10020"]), "gh-sprint")

    def test_duplicates_ignore_case_but_not_type(self):
        rows = fields.duplicate_rows(fields.custom_fields(make_client()))
        self.assertEqual([(r["name"], r["ids"]) for r in rows], [
            ("Story Points", ["customfield_10010", "customfield_10011"]),
            ("Customer Impact", ["customfield_10030", "customfield_10031"])])

    def test_same_name_different_type_is_not_a_duplicate(self):
        a = {"id": "customfield_1", "name": "Owner", "schema": {"custom": "x:userpicker"}}
        b = {"id": "customfield_2", "name": "owner", "schema": {"custom": "x:textfield"}}
        self.assertEqual(fields.duplicates([a, b]), [])


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.session = FakeSession().add("GET", r"/field/search$", load("field_search.json"))
        self.found = fields.search_fields(make_client(self.session))

    def test_requests_usage_data(self):
        params = self.session.calls[0]["params"]
        self.assertEqual(params["type"], "custom")
        self.assertEqual(params["expand"], "lastUsed,screensCount,contextsCount")
        self.assertEqual(len(self.found), 6)

    def test_candidates_are_ranked_by_confidence(self):
        rows = fields.unused_candidates(self.found, now=NOW)
        self.assertEqual([(r["id"], r["confidence"]) for r in rows], [
            ("customfield_10011", "high"), ("customfield_10050", "high"),
            ("customfield_10032", "medium"), ("customfield_10033", "low")])

    def test_field_without_contexts_is_high_confidence_even_when_recent(self):
        field = {"id": "customfield_1", "name": "Ghost", "contextsCount": 0, "screensCount": 2,
                 "lastUsed": {"type": "TRACKED", "value": "2022-04-16T00:00:00.000+0000"}}
        rows = fields.unused_candidates([field], now=NOW)
        self.assertEqual(rows[0]["confidence"], "high")

    def test_untracked_and_recent_fields_are_left_alone(self):
        ids = {r["id"] for r in fields.unused_candidates(self.found, now=NOW)}
        self.assertNotIn("customfield_10010", ids)
        self.assertNotIn("customfield_10040", ids)

    def test_shorter_window_catches_more(self):
        rows = fields.unused_candidates(self.found, now=NOW, stale_days=3)
        self.assertIn("customfield_10010", {r["id"] for r in rows})


class TrashTests(unittest.TestCase):
    def test_dry_run_sends_nothing(self):
        session = FakeSession()
        rows = fields.trash_fields(make_client(session), ["customfield_10011"])
        self.assertEqual(rows[0]["status"], "planned")
        self.assertEqual(session.calls, [])

    def test_apply_deletes_and_reports_failures(self):
        from tests.helpers import FakeResponse
        session = FakeSession()
        session.add("DELETE", r"/field/customfield_10011$", FakeResponse(303, None, {"Location": "/rest/api/3/task/1"}))
        session.add("DELETE", r"/field/customfield_10032$", FakeResponse(400, {"errorMessages": ["Field is locked"]}))
        rows = fields.trash_fields(make_client(session), ["customfield_10011", "customfield_10032"], apply=True)
        self.assertEqual([r["status"] for r in rows], ["trashed", "failed"])
        self.assertIn("Field is locked", rows[1]["detail"])


if __name__ == "__main__":
    unittest.main()
