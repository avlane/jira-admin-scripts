import unittest

from jiraadmin import cleanup, filters
from jiraadmin.client import JiraClient
from tests.helpers import FakeSession, load


def make_client():
    session = FakeSession().add("GET", r"/filter/search$", load("filter_search.json"))
    return JiraClient("https://example.atlassian.net", session=session), session


class CleanupRuleTests(unittest.TestCase):
    def test_owner_states(self):
        self.assertEqual(cleanup.owner_state(None), "missing")
        self.assertEqual(cleanup.owner_state({"accountId": "a", "active": False}), "inactive")
        self.assertEqual(cleanup.owner_state({"accountId": "a", "active": True}), "active")

    def test_findings(self):
        active = {"accountId": "a", "active": True}
        self.assertEqual(cleanup.findings(active, shared=False, favourites=0), ["idle"])
        self.assertEqual(cleanup.findings(active, shared=True, favourites=0), [])
        self.assertEqual(cleanup.findings(active, shared=False, favourites=0, subscriptions=2), [])
        self.assertEqual(cleanup.findings({"accountId": "a", "active": False}, True, 9), ["orphaned"])


class FilterAuditTests(unittest.TestCase):
    def test_requests_owner_and_share_data(self):
        client, session = make_client()
        filters.audit(client)
        self.assertIn("sharePermissions", session.calls[0]["params"]["expand"])

    def test_classification(self):
        client, _ = make_client()
        rows = {r["name"]: r for r in filters.audit(client)}
        self.assertEqual(rows["Open bugs"]["findings"], [])
        self.assertEqual(rows["Dan's backlog"]["findings"], ["orphaned"])
        self.assertEqual(rows["tmp test"]["findings"], ["idle"])
        self.assertEqual(rows["Ops on-call"]["findings"], ["orphaned"])
        self.assertEqual(rows["Sprint health"]["findings"], [])
        self.assertEqual(rows["Open bugs"]["subscriptions"], 1)


if __name__ == "__main__":
    unittest.main()
