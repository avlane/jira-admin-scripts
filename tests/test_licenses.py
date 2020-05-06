import unittest

from jiraadmin import licenses
from jiraadmin.client import JiraClient
from tests.helpers import FakeSession, load


class LicenseTests(unittest.TestCase):
    def rows(self, warn_at=90):
        session = FakeSession().add("GET", r"/applicationrole$", load("applicationrole.json"))
        client = JiraClient("https://example.atlassian.net", session=session)
        return licenses.summarize(licenses.application_roles(client), warn_at)

    def test_percentages(self):
        by_key = {r["key"]: r for r in self.rows()}
        self.assertEqual(by_key["jira-software"]["percent"], 87.0)
        self.assertEqual(by_key["jira-core"]["percent"], 42.0)

    def test_warns_at_threshold(self):
        warned = [r["key"] for r in self.rows(warn_at=85) if r["warning"]]
        self.assertEqual(warned, ["jira-software", "jira-servicedesk"])
        self.assertEqual([r["key"] for r in self.rows() if r["warning"]], ["jira-servicedesk"])

    def test_unlimited_has_no_percentage(self):
        role = {"key": "jira-core", "name": "Jira Core", "userCount": 4, "hasUnlimitedSeats": True}
        row = licenses.summarize([role])[0]
        self.assertIsNone(row["percent"])
        self.assertEqual(row["seats"], "unlimited")
        self.assertFalse(row["warning"])


if __name__ == "__main__":
    unittest.main()
