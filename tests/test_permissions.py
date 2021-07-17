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


if __name__ == "__main__":
    unittest.main()
