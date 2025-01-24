import contextlib
import io
import json
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
        with contextlib.redirect_stderr(io.StringIO()) as err:
            code, text = run(["trash-fields", "--format", "csv"], self.session)
        self.assertIn("dry run: pass --apply", err.getvalue())
        self.assertEqual(code, 0)
        self.assertNotIn("dry run", text)
        self.assertIn("customfield_10011", text)
        self.assertEqual(self.session.calls_to("DELETE", "/field/"), [])

    def test_filters_findings_only(self):
        from tests.helpers import load
        self.session.add("GET", r"/filter/search$", load("filter_search.json"))
        code, text = run(["filters", "--findings-only", "--format", "csv"], self.session)
        self.assertEqual(len(text.splitlines()), 4)

    def test_dashboards(self):
        from tests.helpers import load
        self.session.add("GET", r"/dashboard/search$", load("dashboard_search.json"))
        code, text = run(["dashboards"], self.session)
        self.assertEqual(code, 0)
        self.assertIn("Legacy KPIs", text)

    def test_transfer_filters_dry_run(self):
        from tests.helpers import load
        self.session.add("GET", r"/filter/search$", load("filter_search.json"))
        self.session.add("GET", r"/rest/api/3/user$", load("users_search.json")[0])
        code, text = run(["transfer-filters", "--to", "NEWOWNER", "--format", "csv"], self.session)
        self.assertEqual(code, 0)
        self.assertEqual(text.count("planned"), 1)
        self.assertEqual(text.count("left"), 1)
        self.assertEqual(self.session.calls_to("PUT", "/owner"), [])

    def test_bulk_groups_checks_accounts_before_adding(self):
        import os
        import tempfile
        from tests.helpers import load
        self.session.add("GET", r"/group/member$", {"values": [], "isLast": True, "total": 0})
        self.session.add("GET", r"/user/bulk$", load("user_bulk.json"))
        self.session.add("POST", r"/group/user$", {"name": "devs"})
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "plan.csv")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("action,group,accountId\nadd,devs,5b6a3c1f2d8e4a0b9c7f1e22\nadd,devs,GHOST\n")
            with contextlib.redirect_stderr(io.StringIO()) as err:
                code, text = run(["bulk-groups", path, "--apply", "--format", "json"], self.session)
        self.assertEqual(code, 1)
        self.assertEqual([r["status"] for r in json.loads(text)], ["added", "failed"])
        self.assertIn("summary: 1 added, 1 failed", err.getvalue())
        self.assertIn("unknown or deactivated account", text)

    def test_transfer_dashboards_dry_run(self):
        from tests.helpers import load
        self.session.add("GET", r"/dashboard/search$", load("dashboard_search.json"))
        self.session.add("GET", r"/rest/api/3/user$", load("users_search.json")[0])
        with contextlib.redirect_stderr(io.StringIO()):
            code, text = run(["transfer-dashboards", "--to", "NEW", "--format", "csv"], self.session)
        self.assertEqual(code, 0)
        self.assertEqual(text.splitlines()[1:], ["10001,Dan's scratch,Dan Whitfield,planned,would transfer",
                                                 "10003,Legacy KPIs,(deleted user),planned,would transfer"])

    def test_output_dir_keeps_a_json_copy(self):
        import os
        import tempfile
        from datetime import datetime, timezone
        from unittest import mock
        stamp = datetime(2025, 1, 26, 8, 30, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(cli, "utcnow", return_value=stamp), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            code, text = run(["users", "--output-dir", os.path.join(tmp, "reports"), "--format", "csv"], self.session)
            path = os.path.join(tmp, "reports", "users-20250126T083000Z.json")
            self.assertTrue(os.path.exists(path))
            with open(path, encoding="utf-8") as handle:
                saved = json.load(handle)
        self.assertEqual(len(saved), 5)
        self.assertEqual(text.splitlines()[0], "accountId,status,displayName,emailAddress")
        self.assertIn("saved ", err.getvalue())

    def test_group_members(self):
        from tests.helpers import load
        self.session.add("GET", r"/group/member$", load("group_member.json"))
        code, text = run(["group-members", "jira-administrators", "--format", "csv"], self.session)
        self.assertEqual(len(text.splitlines()), 4)

    def test_missing_configuration_exits_with_2(self):
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {}, clear=True), contextlib.redirect_stderr(io.StringIO()) as err:
            code = cli.main(["users"], out=io.StringIO())
        self.assertEqual(code, 2)
        self.assertIn("JIRA_URL", err.getvalue())

    def test_api_errors_exit_with_2(self):
        from tests.helpers import FakeResponse
        session = FakeSession().add("GET", r"/users/search$", FakeResponse(401, {"message": "Unauthorized"}))
        with contextlib.redirect_stderr(io.StringIO()) as err:
            code, text = run(["users"], session)
        self.assertEqual(code, 2)
        self.assertEqual(text, "")
        self.assertIn("HTTP 401", err.getvalue())

    def test_unknown_command_is_a_usage_error(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as ctx:
            cli.build_parser().parse_args(["frobnicate"])
        self.assertEqual(ctx.exception.code, 2)

    def test_every_command_has_a_summary(self):
        self.assertGreaterEqual(len(cli.COMMANDS), 16)
        self.assertTrue(all(spec["summary"] for spec in cli.COMMANDS.values()))

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
