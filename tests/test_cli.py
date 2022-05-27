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

    def test_roles_findings_only(self):
        from tests.test_roles import make_session
        session = make_session()
        code, text = run(["roles", "--findings-only", "--format", "csv"], session)
        self.assertEqual(code, 0)
        lines = text.splitlines()
        self.assertEqual(lines[0], "project,role,actorType,actor,finding")
        self.assertEqual(len(lines), 5)

    def test_permissions_grants(self):
        from tests.test_permissions import make_session
        code, text = run(["permissions", "--grants", "--format", "csv"], make_session())
        self.assertEqual(len(text.splitlines()), 3)

    def test_trash_fields_dry_run(self):
        from tests.helpers import load
        self.session.add("GET", r"/field/search$", load("field_search.json"))
        code, text = run(["trash-fields", "--format", "csv"], self.session)
        self.assertEqual(code, 0)
        self.assertIn("dry run", text)
        self.assertIn("customfield_10011", text)
        self.assertEqual(self.session.calls_to("DELETE", "/field/"), [])

    def test_group_members(self):
        from tests.helpers import load
        self.session.add("GET", r"/group/member$", load("group_member.json"))
        code, text = run(["group-members", "jira-administrators", "--format", "csv"], self.session)
        self.assertEqual(len(text.splitlines()), 4)

    def test_group_members_needs_a_group(self):
        code, _ = run(["group-members"], self.session)
        self.assertEqual(code, 2)

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
