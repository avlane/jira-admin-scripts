import io
import unittest

from jiraadmin import groups
from jiraadmin.client import JiraClient
from tests.helpers import FakeResponse, FakeSession, load, paged


def make(session):
    return JiraClient("https://example.atlassian.net", session=session)


class MembersTests(unittest.TestCase):
    def test_recorded_page(self):
        session = FakeSession().add("GET", r"/group/member$", load("group_member.json"))
        got = groups.members(make(session), "jira-administrators")
        self.assertEqual([u["displayName"] for u in got], ["Alice Moreau", "Bob Okafor", "Carol Nguyen"])
        self.assertEqual(session.calls[0]["params"]["groupname"], "jira-administrators")
        self.assertEqual(session.calls[0]["params"]["includeInactiveUsers"], "false")

    def test_by_group_id(self):
        session = FakeSession().add("GET", r"/group/member$", load("group_member.json"))
        groups.members(make(session), group_id="a1b2c3d4-0000-4000-8000-000000000001")
        params = session.calls[0]["params"]
        self.assertEqual(params["groupId"], "a1b2c3d4-0000-4000-8000-000000000001")
        self.assertNotIn("groupname", params)

    def test_needs_exactly_one_identifier(self):
        client = make(FakeSession())
        with self.assertRaises(ValueError):
            groups.members(client)
        with self.assertRaises(ValueError):
            groups.members(client, "g", group_id="x")

    def test_walks_pages(self):
        values = load("group_member.json")["values"]
        session = FakeSession().add("GET", r"/group/member$", paged(values, key="values", cap=2))
        got = groups.members(make(session), "g", include_inactive=True)
        self.assertEqual(len(got), 3)
        self.assertEqual(len(session.calls), 2)
        self.assertEqual(session.calls[0]["params"]["includeInactiveUsers"], "true")


CSV_OK = "action,group,accountId\nadd,jira-administrators,5b10ac8d82e05b22cc7d4ef5\nadd,jira-administrators,NEWUSER1\n"


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.session = FakeSession()
        self.session.add("GET", r"/group/member$", load("group_member.json"))
        self.session.add("POST", r"/group/user$", FakeResponse(201, {"name": "jira-administrators"}))

    def test_read_plan(self):
        steps = groups.read_plan(io.StringIO(CSV_OK))
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[1]["accountId"], "NEWUSER1")

    def test_read_plan_rejects_bad_input(self):
        with self.assertRaises(groups.PlanError):
            groups.read_plan(io.StringIO("group,accountId\nx,y\n"))
        with self.assertRaises(groups.PlanError):
            groups.read_plan(io.StringIO("action,group,accountId\nfrob,x,y\n"))
        self.assertEqual(groups.read_plan(io.StringIO("action,group,accountId\nRemove,x,y\n"))[0]["action"], "remove")
        with self.assertRaises(groups.PlanError):
            groups.read_plan(io.StringIO("action,group,accountId\nadd,,y\n"))

    def test_dry_run_changes_nothing(self):
        results = groups.run_plan(make(self.session), groups.read_plan(io.StringIO(CSV_OK)))
        self.assertEqual([r["status"] for r in results], ["skipped", "planned"])
        self.assertEqual(self.session.calls_to("POST", "/group/user"), [])

    def test_apply_adds_missing_members(self):
        results = groups.run_plan(make(self.session), groups.read_plan(io.StringIO(CSV_OK)), apply=True)
        self.assertEqual([r["status"] for r in results], ["skipped", "added"])
        post = self.session.calls_to("POST", "/group/user")[0]
        self.assertEqual(post["params"], {"groupname": "jira-administrators"})
        self.assertEqual(post["json"], {"accountId": "NEWUSER1"})

    def test_remove_only_touches_current_members(self):
        self.session.add("DELETE", r"/group/user$", FakeResponse(200))
        csv_text = ("action,group,accountId\nremove,jira-administrators,5b6a3c1f2d8e4a0b9c7f1e22\n"
                    "remove,jira-administrators,NOTAMEMBER\n")
        steps = groups.read_plan(io.StringIO(csv_text))
        planned = groups.run_plan(make(self.session), steps)
        self.assertEqual([r["status"] for r in planned], ["planned", "skipped"])
        done = groups.run_plan(make(self.session), steps, apply=True)
        self.assertEqual([r["status"] for r in done], ["removed", "skipped"])
        delete = self.session.calls_to("DELETE", "/group/user")[0]
        self.assertEqual(delete["params"], {"groupname": "jira-administrators", "accountId": "5b6a3c1f2d8e4a0b9c7f1e22"})

    def test_unknown_and_deactivated_accounts_are_not_added(self):
        from jiraadmin.users import UserDirectory
        self.session.add("GET", r"/user/bulk$", load("user_bulk.json"))
        client = make(self.session)
        csv_text = ("action,group,accountId\nadd,devs,5d53f3cbc6b9320d9ea5bdc2\n"
                    "add,devs,557058:aa11bb22-cc33-44dd-ee55-ff6677889900\nadd,devs,GHOST\n")
        results = groups.run_plan(client, groups.read_plan(io.StringIO(csv_text)), apply=True, directory=UserDirectory(client))
        self.assertEqual([r["status"] for r in results], ["added", "failed", "failed"])
        self.assertEqual(len(self.session.calls_to("POST", "/group/user")), 1)
        self.assertEqual(len(self.session.calls_to("GET", "/user/bulk")), 1)

    def test_failure_is_reported_not_raised(self):
        self.session.routes = [r for r in self.session.routes if r[0] != "POST"]
        self.session.add("POST", r"/group/user$", FakeResponse(400, {"errorMessages": ["user does not exist"]}))
        results = groups.run_plan(make(self.session), groups.read_plan(io.StringIO(CSV_OK)), apply=True)
        self.assertEqual(results[1]["status"], "failed")
        self.assertIn("400", results[1]["detail"])


if __name__ == "__main__":
    unittest.main()
