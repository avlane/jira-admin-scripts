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


if __name__ == "__main__":
    unittest.main()
