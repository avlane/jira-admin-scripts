import unittest
from datetime import datetime, timezone

from jiraadmin import projects
from jiraadmin.client import JiraClient
from tests.helpers import FakeSession, load

NOW = datetime(2025, 5, 18, 12, 0, tzinfo=timezone.utc)
LAST = {"PLAT": "2025-05-10T09:30:00.000+0000", "OPS": "2023-11-02T16:00:00.000+0000", "OLD": None,
        "ARCH": "2024-05-17T08:00:00.000+0000"}


def search(call):
    key = call["params"]["jql"].split('"')[1]
    updated = LAST[key]
    issues = [{"id": "1", "key": key + "-1", "fields": {"updated": updated}}] if updated else []
    return {"issues": issues, "isLast": True}


def make_client():
    session = FakeSession()
    session.add("GET", r"/project/search$", load("project_search_lead.json"))
    session.add("GET", r"/search/jql$", search)
    return JiraClient("https://example.atlassian.net", session=session), session


class StaleProjectTests(unittest.TestCase):
    def test_report(self):
        client, session = make_client()
        rows = {r["key"]: r for r in projects.stale_report(client, days=365, now=NOW)}
        self.assertEqual(set(rows), {"PLAT", "OPS", "OLD", "ARCH"})
        self.assertEqual(rows["PLAT"]["finding"], "")
        self.assertEqual(rows["OPS"]["finding"], "stale")
        self.assertEqual(rows["OLD"]["finding"], "empty")
        self.assertEqual(rows["ARCH"]["finding"], "stale")
        self.assertEqual(rows["ARCH"]["idleDays"], 366)
        self.assertEqual(rows["OLD"]["leadActive"], False)

    def test_threshold(self):
        client, _ = make_client()
        rows = {r["key"]: r["finding"] for r in projects.stale_report(client, days=400, now=NOW)}
        self.assertEqual(rows["ARCH"], "")
        self.assertEqual(rows["OPS"], "stale")

    def test_one_issue_fetched_per_project(self):
        client, session = make_client()
        projects.stale_report(client, now=NOW)
        calls = session.calls_to("GET", "/search/jql")
        self.assertEqual(len(calls), 4)
        self.assertTrue(all(c["params"]["maxResults"] == 1 for c in calls))
        self.assertIn("ORDER BY updated DESC", calls[0]["params"]["jql"])
        self.assertEqual(session.calls_to("GET", "/project/search")[0]["params"]["expand"], "lead")


class ArchiveTests(unittest.TestCase):
    def test_dry_run_and_apply(self):
        from tests.helpers import FakeResponse
        client, session = make_client()
        session.add("POST", r"/project/OLD/archive$", FakeResponse(204))
        session.add("POST", r"/project/OPS/archive$", FakeResponse(403, {"errorMessages": ["No permission"]}))
        planned = projects.archive_projects(client, ["OLD", "OPS"])
        self.assertEqual([r["status"] for r in planned], ["planned", "planned"])
        self.assertEqual(session.calls, [])
        done = projects.archive_projects(client, ["OLD", "OPS"], apply=True)
        self.assertEqual([r["status"] for r in done], ["archived", "failed"])


if __name__ == "__main__":
    unittest.main()
