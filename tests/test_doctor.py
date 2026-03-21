import unittest

from jiraadmin import doctor
from jiraadmin.client import JiraClient
from tests.helpers import FakeResponse, FakeSession, load

ME = {"accountId": "5b10ac8d82e05b22cc7d4ef5", "displayName": "Alice Moreau", "accountType": "atlassian", "active": True}


def perms(granted):
    return {"permissions": {"ADMINISTER": {"id": "10", "key": "ADMINISTER", "name": "Administer Jira", "type": "GLOBAL",
                                           "description": "Create and administer projects, issue types, fields, workflows, and schemes for all projects.",
                                           "havePermission": granted}}}


def cloud_session():
    return FakeSession().add("GET", r"/serverInfo$", load("serverinfo.json"))


def make_client(session):
    return JiraClient("https://example.atlassian.net", session=session, sleep=lambda s: None)


class DoctorTests(unittest.TestCase):
    def test_all_good(self):
        session = cloud_session().add("GET", r"/myself$", ME).add("GET", r"/mypermissions$", perms(True))
        rows = doctor.run_checks(make_client(session))
        self.assertEqual([(r["check"], r["status"]) for r in rows], [("site", "ok"), ("authentication", "ok"), ("administer jira", "ok")])
        self.assertIn("Example Jira", rows[0]["detail"])
        self.assertIn("Alice Moreau", rows[1]["detail"])
        self.assertEqual(session.calls[2]["params"], {"permissions": "ADMINISTER"})

    def test_bad_credentials_stop_early(self):
        session = cloud_session().add("GET", r"/myself$", FakeResponse(401, {"message": "Unauthorized"}))
        rows = doctor.run_checks(make_client(session))
        self.assertEqual([(r["check"], r["status"]) for r in rows], [("site", "ok"), ("authentication", "fail")])
        self.assertEqual(len(session.calls), 2)

    def test_server_deployments_are_refused(self):
        info = dict(load("serverinfo.json"), deploymentType="Server")
        session = FakeSession().add("GET", r"/serverInfo$", info)
        rows = doctor.run_checks(make_client(session))
        self.assertEqual([(r["check"], r["status"]) for r in rows], [("site", "fail")])
        self.assertIn("target Jira Cloud", rows[0]["detail"])
        self.assertEqual(len(session.calls), 1)

    def test_unreachable_site(self):
        session = FakeSession().add("GET", r"/serverInfo$", FakeResponse(404, "not found"))
        rows = doctor.run_checks(make_client(session))
        self.assertEqual([(r["check"], r["status"]) for r in rows], [("site", "fail")])

    def test_missing_admin_permission(self):
        session = cloud_session().add("GET", r"/myself$", ME).add("GET", r"/mypermissions$", perms(False))
        rows = doctor.run_checks(make_client(session))
        self.assertEqual(rows[2]["status"], "fail")
        self.assertIn("missing", rows[2]["detail"])


if __name__ == "__main__":
    unittest.main()
