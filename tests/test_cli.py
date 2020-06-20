import io
import unittest

from jiraadmin import cli
from jiraadmin.client import JiraClient
from tests.helpers import FakeSession, load, paged


def run(argv, session):
    out = io.StringIO()
    client = JiraClient("https://example.atlassian.net", session=session)
    code = cli.main(argv, client=client, out=out)
    return code, out.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.session = FakeSession().add("GET", r"/users/search$", paged(load("users_search.json")))

    def test_users_lists_humans(self):
        code, text = run(["users"], self.session)
        self.assertEqual(code, 0)
        self.assertEqual(len(text.splitlines()), 7)
        self.assertIn("Alice Moreau", text)
        self.assertNotIn("Deploy Bot", text)

    def test_users_inactive_only(self):
        code, text = run(["users", "--inactive-only", "--format", "csv"], self.session)
        self.assertEqual(text.splitlines(), [
            "accountId,status,displayName,emailAddress",
            "557058:aa11bb22-cc33-44dd-ee55-ff6677889900,inactive,Dan Whitfield,dan.whitfield@example.com"])

    def test_licenses_json(self):
        import json
        from tests.helpers import load
        self.session.add("GET", r"/applicationrole$", load("applicationrole.json"))
        code, text = run(["licenses", "--format", "json"], self.session)
        rows = json.loads(text)
        self.assertEqual([r["key"] for r in rows], ["jira-software", "jira-servicedesk", "jira-core"])
        self.assertTrue(rows[1]["warning"])


if __name__ == "__main__":
    unittest.main()
