import unittest

from jiraadmin import workflows
from jiraadmin.client import JiraClient
from tests.helpers import FakeSession, load
from tests.test_workflowschemes import make_client as scheme_client


def make_client():
    client, session = scheme_client()
    session.add("GET", r"/workflow/search$", load("workflow_search.json"))
    return client, session


class WorkflowReportTests(unittest.TestCase):
    def test_findings(self):
        client, _ = make_client()
        rows = {r["name"]: r for r in workflows.report(client)}
        self.assertEqual(rows["jira"]["finding"], "")
        self.assertEqual(rows["PLAT Workflow"]["finding"], "")
        self.assertEqual(rows["Old Release Flow"]["finding"], "unused")
        self.assertEqual(rows["Retired Flow"]["finding"], "only-in-unused-schemes")
        self.assertEqual(rows["PLAT Bug Workflow"]["statuses"], 3)

    def test_asks_for_schemes_and_statuses(self):
        client, session = make_client()
        workflows.list_workflows(client)
        self.assertEqual(session.calls_to("GET", "/workflow/search")[0]["params"]["expand"], "schemes,statuses")


if __name__ == "__main__":
    unittest.main()
