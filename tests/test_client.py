import unittest

from jiraadmin.client import JiraClient, JiraError
from tests.helpers import FakeResponse, FakeSession


def make(session):
    return JiraClient("https://example.atlassian.net/", session=session)


class ClientTests(unittest.TestCase):
    def test_get_builds_v3_url_and_passes_params(self):
        session = FakeSession().add("GET", r"/rest/api/3/myself$", {"accountId": "abc"})
        data = make(session).get("myself", {"expand": "groups"})
        self.assertEqual(data["accountId"], "abc")
        self.assertEqual(session.calls[0]["url"], "https://example.atlassian.net/rest/api/3/myself")
        self.assertEqual(session.calls[0]["params"], {"expand": "groups"})

    def test_absolute_rest_paths_are_kept(self):
        session = FakeSession().add("GET", r"/rest/webhooks/1.0/webhook$", [])
        make(session).get("/rest/webhooks/1.0/webhook")
        self.assertEqual(session.calls[0]["url"], "https://example.atlassian.net/rest/webhooks/1.0/webhook")

    def test_http_error_raises_with_status(self):
        session = FakeSession().add("GET", r"/myself$", FakeResponse(401, {"message": "Unauthorized"}))
        with self.assertRaises(JiraError) as ctx:
            make(session).get("myself")
        self.assertEqual(ctx.exception.status, 401)

    def test_empty_body_returns_none(self):
        session = FakeSession().add("GET", r"/ping$", FakeResponse(204))
        self.assertIsNone(make(session).request("GET", "ping", expected=(204,)))


if __name__ == "__main__":
    unittest.main()
