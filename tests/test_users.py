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
        session.add("GET", r"/users/search$", paged(load("users_search.json")))
        session.add("GET", r"/rest/api/3/search$", search_route({"5b10ac8d82e05b22cc7d4ef5": 12, "5b6a3c1f2d8e4a0b9c7f1e22": 1}))
        client = JiraClient("https://example.atlassian.net", session=session)
        rows = users.inactive_users(client, days=60)
        self.assertEqual([r["displayName"] for r in rows], ["Carol Nguyen", "Erin Castellano"])
        self.assertEqual(rows[1]["emailAddress"], "")
        jql = session.calls_to("GET", "/rest/api/3/search$")[0]["params"]["jql"]
        self.assertIn("updated >= -60d", jql)

    def test_excluded_accounts_are_not_searched(self):
        session = FakeSession()
        session.add("GET", r"/users/search$", paged(load("users_search.json")))
        session.add("GET", r"/rest/api/3/search$", search_route({}))
        client = JiraClient("https://example.atlassian.net", session=session)
        rows = users.inactive_users(client, exclude={"712020:6f1d2a3b-4c5d-4e6f-8a9b-0c1d2e3f4a5b"})
        self.assertEqual([r["displayName"] for r in rows], ["Alice Moreau", "Bob Okafor", "Erin Castellano"])
        self.assertEqual(len(session.calls_to("GET", "/rest/api/3/search$")), 3)

    def test_progress_ticks_once_per_searched_account(self):
        from jiraadmin.progress import Progress
        import io
        session = FakeSession()
        session.add("GET", r"/users/search$", paged(load("users_search.json")))
        session.add("GET", r"/rest/api/3/search$", search_route({}))
        stream = io.StringIO()
        progress = Progress("inactive", stream=stream, every=2)
        users.inactive_users(JiraClient("https://example.atlassian.net", session=session), progress=progress)
        self.assertEqual(progress.done, 4)

    def test_account_list_file(self):
        import io
        text = "# service accounts\n5b10ac8d82e05b22cc7d4ef5\n\n  5b6a3c1f2d8e4a0b9c7f1e22  # on leave\n"
        self.assertEqual(users.read_account_list(io.StringIO(text)), {"5b10ac8d82e05b22cc7d4ef5", "5b6a3c1f2d8e4a0b9c7f1e22"})

    def test_limit_stops_early(self):
        session = FakeSession()
        session.add("GET", r"/users/search$", paged([u for u in load("users_search.json") if u.get("emailAddress")]))
        session.add("GET", r"/rest/api/3/search$", search_route({}))
        client = JiraClient("https://example.atlassian.net", session=session)
        self.assertEqual(len(users.inactive_users(client, limit=2)), 2)


if __name__ == "__main__":
    unittest.main()


class AssignableTests(unittest.TestCase):
    def client(self, user):
        session = FakeSession().add("GET", r"/rest/api/3/user$", user)
        return JiraClient("https://example.atlassian.net", session=session), session

    def test_active_human_is_accepted(self):
        client, session = self.client(load("users_search.json")[0])
        self.assertEqual(users.require_assignable(client, "5b10ac8d82e05b22cc7d4ef5")["displayName"], "Alice Moreau")
        self.assertEqual(session.calls[0]["params"], {"accountId": "5b10ac8d82e05b22cc7d4ef5"})

    def test_inactive_and_app_accounts_are_refused(self):
        from jiraadmin.client import JiraError
        for index in (3, 5):
            client, _ = self.client(load("users_search.json")[index])
            with self.assertRaises(JiraError):
                users.require_assignable(client, "x")


class DirectoryTests(unittest.TestCase):
    def setUp(self):
        self.session = FakeSession().add("GET", r"/user/bulk$", load("user_bulk.json"))
        self.directory = users.UserDirectory(JiraClient("https://example.atlassian.net", session=self.session))

    def test_answers_are_cached(self):
        self.assertTrue(self.directory.is_active("5b10ac8d82e05b22cc7d4ef5"))
        self.assertFalse(self.directory.is_active("557058:aa11bb22-cc33-44dd-ee55-ff6677889900"))
        self.assertEqual(len(self.session.calls), 2)
        self.directory.get("5b10ac8d82e05b22cc7d4ef5")
        self.assertEqual(len(self.session.calls), 2)

    def test_prefetch_batches_and_deduplicates(self):
        ids = ["id%d" % n for n in range(120)] + ["id1", "id2"]
        self.directory.prefetch(ids)
        sizes = [len(c["params"]["accountId"]) for c in self.session.calls]
        self.assertEqual(sizes, [50, 50, 20])
        self.directory.prefetch(ids)
        self.assertEqual(len(self.session.calls), 3)

    def test_unknown_accounts_are_not_active_and_asked_once(self):
        self.assertIsNone(self.directory.get("nobody"))
        self.assertFalse(self.directory.is_active("nobody"))
        self.assertEqual(len(self.session.calls), 1)
