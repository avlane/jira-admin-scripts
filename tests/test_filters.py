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


class TransferPlanTests(unittest.TestCase):
    def test_unused_orphans_are_left_alone(self):
        client, _ = make_client()
        plan = {p["name"]: p for p in filters.transfer_plan(filters.audit(client))}
        self.assertEqual(set(plan), {"Dan's backlog", "Ops on-call"})
        self.assertEqual(plan["Ops on-call"]["action"], "transfer")
        self.assertEqual(plan["Dan's backlog"]["action"], "leave")

    def test_favourite_threshold(self):
        client, _ = make_client()
        rows = filters.audit(client)
        strict = {p["name"]: p["action"] for p in filters.transfer_plan(rows, min_favourites=50)}
        self.assertEqual(strict["Ops on-call"], "transfer")  # still shared
        rows = [dict(r, shared=False) for r in rows]
        strict = {p["name"]: p["action"] for p in filters.transfer_plan(rows, min_favourites=50)}
        self.assertEqual(strict["Ops on-call"], "leave")


class TransferTests(unittest.TestCase):
    def test_dry_run(self):
        client, session = make_client()
        rows = filters.transfer_owner(client, ["10001"], "NEWOWNER")
        self.assertEqual(rows, [{"id": "10001", "status": "planned", "detail": "would transfer"}])
        self.assertEqual(session.calls, [])

    def test_apply_puts_new_owner(self):
        from tests.helpers import FakeResponse
        client, session = make_client()
        session.add("PUT", r"/filter/10001/owner$", FakeResponse(204))
        session.add("PUT", r"/filter/10004/owner$", FakeResponse(403, {"errorMessages": ["Forbidden"]}))
        rows = filters.transfer_owner(client, ["10001", "10004"], "NEWOWNER", apply=True)
        self.assertEqual([r["status"] for r in rows], ["transferred", "failed"])
        self.assertEqual(session.calls_to("PUT", "/filter/10001/owner")[0]["json"], {"accountId": "NEWOWNER"})


if __name__ == "__main__":
    unittest.main()
