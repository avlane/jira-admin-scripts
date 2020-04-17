import unittest

from jiraadmin import users
from jiraadmin.client import JiraClient
from tests.helpers import FakeSession, load, paged


def client_with_users():
    session = FakeSession().add("GET", r"/users/search$", paged(load("users_search.json")))
    return JiraClient("https://example.atlassian.net", session=session)


class UserTests(unittest.TestCase):
    def test_iter_users_returns_everything(self):
        self.assertEqual(len(list(users.iter_users(client_with_users()))), 7)

    def test_human_users_skip_apps_and_customers(self):
        names = [u["displayName"] for u in users.human_users(client_with_users())]
        self.assertEqual(names, ["Alice Moreau", "Bob Okafor", "Carol Nguyen", "Dan Whitfield", "Erin Castellano"])


def search_route(totals):
    def handler(call):
        jql = call["params"]["jql"]
        for account_id, total in totals.items():
            if account_id in jql:
                return {"startAt": 0, "maxResults": 0, "total": total, "issues": []}
        return {"startAt": 0, "maxResults": 0, "total": 0, "issues": []}
    return handler


class InactiveTests(unittest.TestCase):
    def test_only_accounts_without_recent_issues_are_reported(self):
        session = FakeSession()
        session.add("GET", r"/users/search$", paged([u for u in load("users_search.json") if u.get("emailAddress")]))
        session.add("GET", r"/rest/api/3/search$", search_route({"5b10ac8d82e05b22cc7d4ef5": 12, "5b6a3c1f2d8e4a0b9c7f1e22": 1}))
        client = JiraClient("https://example.atlassian.net", session=session)
        rows = users.inactive_users(client, days=60)
        self.assertEqual([r["displayName"] for r in rows], ["Carol Nguyen"])
        jql = session.calls_to("GET", "/rest/api/3/search$")[0]["params"]["jql"]
        self.assertIn("updated >= -60d", jql)

    def test_limit_stops_early(self):
        session = FakeSession()
        session.add("GET", r"/users/search$", paged([u for u in load("users_search.json") if u.get("emailAddress")]))
        session.add("GET", r"/rest/api/3/search$", search_route({}))
        client = JiraClient("https://example.atlassian.net", session=session)
        self.assertEqual(len(users.inactive_users(client, limit=2)), 2)


if __name__ == "__main__":
    unittest.main()
