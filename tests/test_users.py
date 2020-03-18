import unittest

from jiraadmin import users
from jiraadmin.client import JiraClient
from tests.helpers import FakeSession, load, paged


def client_with_users():
    session = FakeSession().add("GET", r"/users/search$", paged(load("users_search.json")))
    return JiraClient("https://example.atlassian.net", session=session)


class UserTests(unittest.TestCase):
    def test_iter_users_returns_everything(self):
        self.assertEqual(len(list(users.iter_users(client_with_users()))), 7)

    def test_human_users_skip_apps_and_customers(self):
        names = [u["displayName"] for u in users.human_users(client_with_users())]
        self.assertEqual(names, ["Alice Moreau", "Bob Okafor", "Carol Nguyen", "Dan Whitfield", "Erin Castellano"])


if __name__ == "__main__":
    unittest.main()
