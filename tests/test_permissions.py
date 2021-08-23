import unittest

from jiraadmin import permissions
from jiraadmin.client import JiraClient
from tests.helpers import FakeSession, load


def make_session():
    s = FakeSession()
    s.add("GET", r"/project/search$", load("project_search.json"))
    s.add("GET", r"/api/3/permissionscheme$", load("permissionscheme.json"))
    s.add("GET", r"/project/PLAT/permissionscheme$", load("project_plat_permissionscheme.json"))
    s.add("GET", r"/project/OPS/permissionscheme$", load("project_ops_permissionscheme.json"))
    return s


class SchemeTests(unittest.TestCase):
    def setUp(self):
        self.session = make_session()
        self.client = JiraClient("https://example.atlassian.net", session=self.session)

    def test_schemes_are_requested_with_permissions(self):
        self.assertEqual(len(permissions.schemes(self.client)), 3)
        self.assertEqual(self.session.calls[0]["params"], {"expand": "permissions"})

    def test_usage_maps_schemes_to_classic_projects(self):
        self.assertEqual(permissions.scheme_usage(self.client), {10000: ["PLAT"], 10001: ["OPS"]})

    def test_summary_marks_unused_schemes(self):
        rows = permissions.scheme_summary(self.client)
        self.assertEqual([(r["name"], r["projects"], r["unused"]) for r in rows], [
            ("Default Permission Scheme", 1, False), ("Open Intake", 1, False), ("Legacy Scheme", 0, True)])


class GrantTests(unittest.TestCase):
    def test_open_and_direct_grants_are_flagged(self):
        client = JiraClient("https://example.atlassian.net", session=make_session())
        rows = permissions.grant_report(client)
        self.assertEqual([(r["scheme"], r["permission"], r["finding"]) for r in rows], [
            ("Open Intake", "CREATE_ISSUES", "anyone"),
            ("Open Intake", "DELETE_ISSUES", "direct-user")])

    def test_browse_for_anyone_is_not_flagged(self):
        scheme = {"name": "Public", "permissions": [{"holder": {"type": "anyone"}, "permission": "BROWSE_PROJECTS"}]}
        self.assertEqual(list(permissions.grant_findings(scheme)), [])

    def test_everyone_with_a_licence_can_delete(self):
        scheme = {"name": "Loose", "permissions": [{"holder": {"type": "applicationRole"}, "permission": "DELETE_ISSUES"}]}
        self.assertEqual(list(permissions.grant_findings(scheme)), [("DELETE_ISSUES", "applicationRole", "broad-risky")])


if __name__ == "__main__":
    unittest.main()
