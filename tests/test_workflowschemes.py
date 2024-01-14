import unittest

from jiraadmin import workflowschemes
from jiraadmin.client import JiraClient
from tests.helpers import FakeSession, load


def make_client():
    session = FakeSession()
    session.add("GET", r"/project/search$", load("project_search.json"))
    session.add("GET", r"/rest/api/3/workflowscheme$", load("workflowscheme.json"))
    session.add("GET", r"/workflowscheme/project$", load("workflowscheme_project.json"))
    return JiraClient("https://example.atlassian.net", session=session), session


class WorkflowSchemeTests(unittest.TestCase):
    def test_report(self):
        client, _ = make_client()
        rows = workflowschemes.report(client)
        self.assertEqual([(r["name"], r["projects"], r["unused"]) for r in rows], [
            ("PLAT Workflow Scheme", ["PLAT"], False), ("OPS Workflow Scheme", ["OPS"], False),
            ("Retired Workflow Scheme", [], True)])
        self.assertEqual(rows[0]["workflows"], ["PLAT Bug Workflow", "PLAT Workflow"])

    def test_only_classic_projects_are_asked_about(self):
        client, session = make_client()
        workflowschemes.report(client)
        call = session.calls_to("GET", "/workflowscheme/project")[0]
        self.assertEqual(call["params"]["projectId"], ["10000", "10001"])

    def test_default_scheme_without_an_id_is_matched_by_name(self):
        client, session = make_client()
        default = {"name": "Default Workflow Scheme", "defaultWorkflow": "jira", "issueTypeMappings": {}, "draft": False}
        session.routes = [r for r in session.routes if "workflowscheme" not in r[1].pattern]
        session.add("GET", r"/rest/api/3/workflowscheme$", {"maxResults": 50, "startAt": 0, "total": 1, "isLast": True, "values": [default]})
        session.add("GET", r"/workflowscheme/project$", {"maxResults": 50, "startAt": 0, "total": 1, "isLast": True,
                                                         "values": [{"projectIds": ["10000", "10001"], "workflowScheme": default}]})
        rows = workflowschemes.report(client)
        self.assertEqual(rows[0]["projects"], ["PLAT", "OPS"])
        self.assertEqual(rows[0]["id"], "")


if __name__ == "__main__":
    unittest.main()
