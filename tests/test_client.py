import unittest

from jiraadmin.client import JiraClient, JiraError
from tests.helpers import FakeResponse, FakeSession, Seq


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


class RateLimitTests(unittest.TestCase):
    def test_retries_after_the_advertised_delay(self):
        limited = FakeResponse(429, {"message": "Rate limit exceeded"}, {"Retry-After": "7"})
        session = FakeSession().add("GET", r"/myself$", Seq(limited, limited, {"accountId": "abc"}))
        sleeps = []
        client = JiraClient("https://example.atlassian.net", session=session, sleep=sleeps.append)
        self.assertEqual(client.get("myself")["accountId"], "abc")
        self.assertEqual(sleeps, [7, 7])
        self.assertEqual(len(session.calls), 3)

    def test_waits_are_logged(self):
        limited = FakeResponse(429, None, {"Retry-After": "3"})
        session = FakeSession().add("GET", r"/myself$", Seq(limited, {"ok": True}))
        client = JiraClient("https://example.atlassian.net", session=session, sleep=lambda s: None)
        with self.assertLogs("jiraadmin.client", level="WARNING") as captured:
            client.get("myself")
        self.assertIn("waiting 3s (retry 1 of 5)", captured.output[0])

    def test_missing_header_uses_default_delay(self):
        session = FakeSession().add("GET", r"/myself$", Seq(FakeResponse(429), {"ok": True}))
        sleeps = []
        JiraClient("https://example.atlassian.net", session=session, sleep=sleeps.append).get("myself")
        self.assertEqual(sleeps, [5])

    def test_gives_up_after_max_retries(self):
        session = FakeSession().add("GET", r"/myself$", FakeResponse(429, None, {"Retry-After": "1"}))
        client = JiraClient("https://example.atlassian.net", session=session, max_retries=2, sleep=lambda s: None)
        with self.assertRaises(JiraError) as ctx:
            client.get("myself")
        self.assertEqual(ctx.exception.status, 429)
        self.assertEqual(len(session.calls), 3)


if __name__ == "__main__":
    unittest.main()
