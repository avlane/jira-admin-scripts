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
        self.assertEqual([r["id"] for r in rows], [2, 3, 12])
        self.assertTrue(rows[2]["note"].startswith("only in a screen scheme nothing uses"))
        self.assertTrue(rows[0]["note"].startswith("in no screen scheme;"))

    def test_unused_screen_schemes(self):
        client, _ = make_client()
        self.assertEqual([s["name"] for s in screens.unused_screen_schemes(screens.screen_schemes(client))], ["Hotfix Screen Scheme"])


class IssueTypeSchemeTests(unittest.TestCase):
    def setUp(self):
        self.client, self.session = make_client()
        self.session.add("GET", r"/project/search$", load("project_search.json"))
        self.session.add("GET", r"/issuetypescreenscheme$", load("issuetypescreenscheme.json"))
        self.session.add("GET", r"/issuetypescreenscheme/mapping$", load("issuetypescreenscheme_mapping.json"))
        self.session.add("GET", r"/issuetypescreenscheme/project$", load("issuetypescreenscheme_project.json"))

    def test_report(self):
        rows = screens.issue_type_scheme_report(self.client)
        self.assertEqual([(r["id"], r["projects"], r["screenSchemes"]) for r in rows], [
            ("1", [], ["Default Screen Scheme"]), ("10000", ["PLAT"], ["PLAT Screen Scheme"]),
            ("10001", ["OPS"], ["OPS Screen Scheme"])])
        self.assertFalse(any(r["unused"] for r in rows))

    def test_project_ids_are_sent_as_a_repeated_parameter(self):
        screens.issue_type_scheme_report(self.client)
        call = self.session.calls_to("GET", "/issuetypescreenscheme/project")[0]
        self.assertEqual(call["params"]["projectId"], ["10000", "10001"])

    def test_batches_of_fifty(self):
        screens.project_associations(self.client, [str(n) for n in range(120)])
        calls = self.session.calls_to("GET", "/issuetypescreenscheme/project")
        self.assertEqual([len(c["params"]["projectId"]) for c in calls], [50, 50, 20])


if __name__ == "__main__":
    unittest.main()
