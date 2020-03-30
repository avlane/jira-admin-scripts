import io
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
        self.assertEqual(len(text.splitlines()), 5)
        self.assertIn("Alice Moreau", text)

    def test_users_inactive_only(self):
        code, text = run(["users", "--inactive-only"], self.session)
        self.assertEqual(text.splitlines(), [
            "557058:aa11bb22-cc33-44dd-ee55-ff6677889900\tinactive\tDan Whitfield\tdan.whitfield@example.com"])


if __name__ == "__main__":
    unittest.main()
