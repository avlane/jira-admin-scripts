import unittest

from jiraadmin import dashboards
from jiraadmin.client import JiraClient
from tests.helpers import FakeSession, load


class DashboardAuditTests(unittest.TestCase):
    def setUp(self):
        self.session = FakeSession().add("GET", r"/dashboard/search$", load("dashboard_search.json"))
        self.rows = {r["name"]: r for r in dashboards.audit(JiraClient("https://example.atlassian.net", session=self.session))}

    def test_classification(self):
        self.assertEqual(self.rows["Platform overview"]["findings"], [])
        self.assertEqual(self.rows["Dan's scratch"]["findings"], ["orphaned"])
        self.assertEqual(self.rows["Release tracker"]["findings"], ["idle"])

    def test_deleted_owner_is_orphaned(self):
        row = self.rows["Legacy KPIs"]
        self.assertEqual(row["ownerState"], "missing")
        self.assertEqual(row["owner"], "(deleted user)")
        self.assertEqual(row["findings"], ["orphaned"])

    def test_expands_owner(self):
        self.assertIn("owner", self.session.calls[0]["params"]["expand"])


class ChangeOwnerTests(unittest.TestCase):
    def client(self, response=None):
        from tests.helpers import FakeResponse
        session = FakeSession().add("PUT", r"/dashboard/bulk/edit$", response or FakeResponse(200, {}))
        return JiraClient("https://example.atlassian.net", session=session), session

    def test_dry_run(self):
        client, session = self.client()
        rows = dashboards.change_owner(client, ["10001"], "NEW")
        self.assertEqual(rows[0]["status"], "planned")
        self.assertEqual(session.calls, [])

    def test_one_request_for_all_dashboards(self):
        client, session = self.client()
        rows = dashboards.change_owner(client, ["10001", "10003"], "NEW", apply=True)
        self.assertEqual([r["status"] for r in rows], ["transferred", "transferred"])
        body = session.calls[0]["json"]
        self.assertEqual(body["action"], "changeOwner")
        self.assertEqual(body["entityIds"], [10001, 10003])
        self.assertEqual(body["changeOwnerDetails"], {"autofixName": True, "newOwner": "NEW"})

    def test_failure_marks_every_dashboard(self):
        from tests.helpers import FakeResponse
        client, _ = self.client(FakeResponse(403, {"errorMessages": ["Forbidden"]}))
        rows = dashboards.change_owner(client, ["10001", "10003"], "NEW", apply=True)
        self.assertEqual([r["status"] for r in rows], ["failed", "failed"])

    def test_nothing_to_do(self):
        client, session = self.client()
        self.assertEqual(dashboards.change_owner(client, [], "NEW", apply=True), [])
        self.assertEqual(session.calls, [])


if __name__ == "__main__":
    unittest.main()
