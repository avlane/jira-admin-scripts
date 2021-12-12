import unittest

from jiraadmin.client import JiraClient
from tests.helpers import FakeSession, load, paged


class PaginationTests(unittest.TestCase):
    def client(self, handler):
        session = FakeSession().add("GET", r"/users/search$", handler)
        return JiraClient("https://example.atlassian.net", session=session), session

    def test_bare_array_is_walked_page_by_page(self):
        users = load("users_search.json")
        client, session = self.client(paged(users))
        got = list(client.paginate("users/search", page_size=3))
        self.assertEqual([u["accountId"] for u in got], [u["accountId"] for u in users])
        self.assertEqual([c["params"]["startAt"] for c in session.calls], [0, 3, 6, 7])

    def test_paged_object_stops_on_is_last(self):
        users = load("users_search.json")
        client, session = self.client(paged(users, key="values"))
        got = list(client.paginate("users/search", page_size=4))
        self.assertEqual(len(got), 7)
        self.assertEqual(len(session.calls), 2)

    def test_server_side_page_cap_is_not_mistaken_for_the_end(self):
        users = load("users_search.json")
        client, session = self.client(paged(users, cap=2))
        got = list(client.paginate("users/search", page_size=100))
        self.assertEqual(len(got), 7)
        self.assertEqual([c["params"]["startAt"] for c in session.calls], [0, 2, 4, 6, 7])

    def test_empty_result(self):
        client, session = self.client(paged([], key="values"))
        self.assertEqual(list(client.paginate("users/search")), [])
        self.assertEqual(len(session.calls), 1)


if __name__ == "__main__":
    unittest.main()
