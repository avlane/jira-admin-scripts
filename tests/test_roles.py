import unittest

from jiraadmin import roles
from jiraadmin.client import JiraClient
from tests.helpers import FakeSession, load


def make_session():
    s = FakeSession()
    s.add("GET", r"/project/search$", load("project_search.json"))
    s.add("GET", r"/project/PLAT/role$", load("project_roles_plat.json"))
    s.add("GET", r"/project/OPS/role$", load("project_roles_ops.json"))
    s.add("GET", r"/user/bulk$", load("user_bulk.json"))
    for suffix, name in (("PLAT/role/10002", "role_plat_10002"), ("PLAT/role/10001", "role_plat_10001"),
                         ("PLAT/role/10000", "role_plat_10000"), ("PLAT/role/10100", "role_plat_10100"),
                         ("OPS/role/10002", "role_ops_10002"), ("OPS/role/10001", "role_ops_10001")):
        s.add("GET", r"/project/" + suffix + "$", load(name + ".json"))
    return s


class RoleTests(unittest.TestCase):
    def setUp(self):
        self.session = make_session()
        self.client = JiraClient("https://example.atlassian.net", session=self.session)

    def test_role_ids_are_parsed_from_urls(self):
        self.assertEqual(roles.project_roles(self.client, "OPS"), {"Administrators": 10002, "Developers": 10001})

    def test_audit_flags_direct_users_and_empty_roles(self):
        rows = roles.audit(self.client)
        findings = [(r["project"], r["role"], r["finding"]) for r in rows if r["finding"]]
        self.assertEqual(findings, [
            ("PLAT", "Developers", "direct-user"), ("PLAT", "Developers", "direct-user"),
            ("PLAT", "Users", "empty-role"), ("OPS", "Administrators", "direct-user")])

    def test_check_users_reports_deactivated_accounts(self):
        rows = roles.audit(self.client, check_users=True)
        findings = [(r["project"], r["actor"], r["finding"]) for r in rows if r["actorType"] == "user"]
        self.assertEqual(findings, [("PLAT", "Alice Moreau", "direct-user"), ("PLAT", "Dan Whitfield", "inactive-user"),
                                    ("OPS", "Bob Okafor", "direct-user")])
        call = self.session.calls_to("GET", "/user/bulk")[0]
        self.assertEqual(sorted(call["params"]["accountId"]), sorted(["5b10ac8d82e05b22cc7d4ef5", "557058:aa11bb22-cc33-44dd-ee55-ff6677889900",
                                                                   "5b6a3c1f2d8e4a0b9c7f1e22"]))

    def test_unknown_accounts_count_as_inactive(self):
        self.session.routes = [r for r in self.session.routes if "bulk" not in r[1].pattern]
        self.session.add("GET", r"/user/bulk$", {"values": []})
        rows = roles.audit(self.client, projects=["OPS"], check_users=True)
        self.assertEqual([r["finding"] for r in rows if r["actorType"] == "user"], ["inactive-user"])

    def test_without_check_users_nobody_is_looked_up(self):
        roles.audit(self.client)
        self.assertEqual(self.session.calls_to("GET", "/user/bulk"), [])

    def test_team_managed_projects_and_addon_roles_are_skipped(self):
        rows = roles.audit(self.client)
        self.assertNotIn("NEXT", {r["project"] for r in rows})
        self.assertNotIn("atlassian-addons-project-access", {r["role"] for r in rows})
        self.assertEqual(self.session.calls_to("GET", "/project/NEXT"), [])

    def test_explicit_project_list_skips_project_search(self):
        rows = roles.audit(self.client, projects=["OPS"])
        self.assertEqual({r["project"] for r in rows}, {"OPS"})
        self.assertEqual(self.session.calls_to("GET", "/project/search"), [])

    def test_group_rows_carry_group_id(self):
        row = [r for r in roles.audit(self.client, projects=["OPS"]) if r["actorType"] == "group"][0]
        self.assertEqual(row["actor"], "ops-agents")
        self.assertEqual(row["actorId"], "a1b2c3d4-0000-4000-8000-000000000003")


if __name__ == "__main__":
    unittest.main()
