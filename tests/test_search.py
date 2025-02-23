import unittest

from jiraadmin import search
from jiraadmin.client import JiraClient
from tests.helpers import FakeSession, Seq, load


def make_client():
    session = FakeSession().add("GET", r"/search/jql$", Seq(load("search_jql_page1.json"), load("search_jql_page2.json")))
    return JiraClient("https://example.atlassian.net", session=session), session


class SearchTests(unittest.TestCase):
    def test_follows_next_page_token(self):
        client, session = make_client()
        keys = [i["key"] for i in search.iter_issues(client, "project = PLAT", fields=("key", "updated"))]
        self.assertEqual(keys, ["PLAT-1", "PLAT-2", "PLAT-3"])
        first, second = [c["params"] for c in session.calls]
        self.assertNotIn("nextPageToken", first)
        self.assertEqual(second["nextPageToken"], "CAEaAggC")
        self.assertEqual(first["fields"], "key,updated")
        self.assertEqual(second["jql"], "project = PLAT")

    def test_count_walks_every_page(self):
        client, session = make_client()
        self.assertEqual(search.count_issues(client, "project = PLAT"), 3)
        self.assertEqual(len(session.calls), 2)

    def test_count_with_limit_stops_early(self):
        client, session = make_client()
        self.assertEqual(search.count_issues(client, "project = PLAT", limit=1), 1)
        self.assertEqual(len(session.calls), 1)
        self.assertEqual(session.calls[0]["params"]["maxResults"], 1)

    def test_no_results(self):
        session = FakeSession().add("GET", r"/search/jql$", {"issues": [], "isLast": True})
        client = JiraClient("https://example.atlassian.net", session=session)
        self.assertEqual(search.count_issues(client, "project = NONE"), 0)


class ApproximateCountTests(unittest.TestCase):
    def test_posts_the_query_and_reads_count(self):
        session = FakeSession().add("POST", r"/search/approximate-count$", {"count": 1234})
        client = JiraClient("https://example.atlassian.net", session=session)
        self.assertEqual(search.approximate_count(client, "project = PLAT"), 1234)
        self.assertEqual(session.calls[0]["json"], {"jql": "project = PLAT"})


if __name__ == "__main__":
    unittest.main()
