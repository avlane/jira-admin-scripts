import unittest

from jiraadmin import screens
from jiraadmin.client import JiraClient
from tests.helpers import FakeSession, load


def make_client():
    session = FakeSession()
    session.add("GET", r"/rest/api/3/screens$", load("screens.json"))
    session.add("GET", r"/rest/api/3/screenscheme$", load("screenscheme.json"))
    return JiraClient("https://example.atlassian.net", session=session), session


class ScreenTests(unittest.TestCase):
    def test_listing_uses_the_maximum_page_size(self):
        client, session = make_client()
        self.assertEqual(len(screens.list_screens(client)), 7)
        self.assertEqual(session.calls[0]["params"]["maxResults"], 100)

    def test_referenced_ids(self):
        client, _ = make_client()
        self.assertEqual(screens.referenced_screen_ids(screens.screen_schemes(client)), {1, 10, 11, 12, 13})

    def test_unused_screens(self):
        client, _ = make_client()
        rows = screens.unused_screens(screens.list_screens(client), screens.screen_schemes(client))
        self.assertEqual([r["id"] for r in rows], [2, 3])


if __name__ == "__main__":
    unittest.main()
