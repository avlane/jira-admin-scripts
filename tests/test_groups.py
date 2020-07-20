import unittest

from jiraadmin import groups
from jiraadmin.client import JiraClient
from tests.helpers import FakeSession, load, paged


def make(session):
    return JiraClient("https://example.atlassian.net", session=session)


class MembersTests(unittest.TestCase):
    def test_recorded_page(self):
        session = FakeSession().add("GET", r"/group/member$", load("group_member.json"))
        got = groups.members(make(session), "jira-administrators")
        self.assertEqual([u["displayName"] for u in got], ["Alice Moreau", "Bob Okafor", "Carol Nguyen"])
        self.assertEqual(session.calls[0]["params"]["groupname"], "jira-administrators")
        self.assertEqual(session.calls[0]["params"]["includeInactiveUsers"], "false")

    def test_walks_pages(self):
        values = load("group_member.json")["values"]
        session = FakeSession().add("GET", r"/group/member$", paged(values, key="values", cap=2))
        got = groups.members(make(session), "g", include_inactive=True)
        self.assertEqual(len(got), 3)
        self.assertEqual(len(session.calls), 2)
        self.assertEqual(session.calls[0]["params"]["includeInactiveUsers"], "true")


if __name__ == "__main__":
    unittest.main()
