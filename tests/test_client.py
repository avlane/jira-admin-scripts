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

    def test_auth_failures_explain_what_to_check(self):
        for status, hint in ((401, "API token"), (403, "Administer Jira")):
            session = FakeSession().add("GET", r"/myself$", FakeResponse(status, {"message": "no"}))
            with self.assertRaises(JiraError) as ctx:
                make(session).get("myself")
            self.assertIn(hint, str(ctx.exception))

    def test_other_errors_have_no_hint(self):
        session = FakeSession().add("GET", r"/myself$", FakeResponse(404, {"message": "gone"}))
        with self.assertRaises(JiraError) as ctx:
            make(session).get("myself")
        self.assertNotIn("(check", str(ctx.exception))

    def test_empty_body_returns_none(self):
        session = FakeSession().add("GET", r"/ping$", FakeResponse(204))
        self.assertIsNone(make(session).request("GET", "ping", expected=(204,)))


class NearLimitTests(unittest.TestCase):
    def test_pauses_until_the_reset_time_when_near_the_limit(self):
        from datetime import datetime, timedelta, timezone
        reset = (datetime.now(timezone.utc) + timedelta(seconds=4, milliseconds=500)).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")
        near = FakeResponse(200, {"ok": True}, {"X-RateLimit-NearLimit": "true", "X-RateLimit-Reset": reset, "X-RateLimit-Remaining": "12"})
        session = FakeSession().add("GET", r"/ping$", near)
        sleeps = []
        JiraClient("https://example.atlassian.net", session=session, sleep=sleeps.append).get("ping")
        self.assertEqual(len(sleeps), 1)
        self.assertTrue(3 <= sleeps[0] <= 5)

    def test_pause_is_capped(self):
        near = FakeResponse(200, {"ok": True}, {"X-RateLimit-NearLimit": "true", "X-RateLimit-Reset": "2999-01-01T00:00:00Z"})
        session = FakeSession().add("GET", r"/ping$", near)
        sleeps = []
        JiraClient("https://example.atlassian.net", session=session, sleep=sleeps.append).get("ping")
        self.assertEqual(sleeps, [10])

    def test_unparsable_reset_pauses_a_second(self):
        near = FakeResponse(200, {"ok": True}, {"X-RateLimit-NearLimit": "true", "X-RateLimit-Reset": "tomorrow"})
        session = FakeSession().add("GET", r"/ping$", near)
        sleeps = []
        JiraClient("https://example.atlassian.net", session=session, sleep=sleeps.append).get("ping")
        self.assertEqual(sleeps, [1])

    def test_no_headers_no_pause(self):
        session = FakeSession().add("GET", r"/ping$", FakeResponse(200, {"ok": True}, {"X-RateLimit-Remaining": "900"}))
        sleeps = []
        JiraClient("https://example.atlassian.net", session=session, sleep=sleeps.append).get("ping")
        self.assertEqual(sleeps, [])

    def test_seconds_until(self):
        from datetime import datetime, timezone
        from jiraadmin.client import seconds_until
        now = datetime(2025, 7, 13, 10, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(seconds_until("2025-07-13T10:00:05Z", now), 5)
        self.assertEqual(seconds_until("2025-07-13T09:00:00Z", now), 0)
        self.assertIsNone(seconds_until(None, now))


class PacingTests(unittest.TestCase):
    def test_requests_are_spaced_out(self):
        class Time:
            now = 100.0

            def clock(self):
                return self.now

            def sleep(self, seconds):
                self.now += seconds

        t = Time()
        session = FakeSession().add("GET", r"/ping$", {"ok": True})
        client = JiraClient("https://example.atlassian.net", session=session, min_interval=0.5, clock=t.clock, sleep=t.sleep)
        client.get("ping")
        t.now += 0.2
        client.get("ping")
        self.assertAlmostEqual(t.now, 100.5)
        t.now += 5
        client.get("ping")
        self.assertAlmostEqual(t.now, 105.5)

    def test_no_pacing_by_default(self):
        sleeps = []
        session = FakeSession().add("GET", r"/ping$", {"ok": True})
        client = JiraClient("https://example.atlassian.net", session=session, sleep=sleeps.append)
        client.get("ping")
        client.get("ping")
        self.assertEqual(sleeps, [])


class TransientErrorTests(unittest.TestCase):
    def test_gateway_errors_are_retried_with_backoff(self):
        session = FakeSession().add("GET", r"/myself$", Seq(FakeResponse(503), FakeResponse(502), {"ok": True}))
        sleeps = []
        client = JiraClient("https://example.atlassian.net", session=session, sleep=sleeps.append)
        self.assertEqual(client.get("myself"), {"ok": True})
        self.assertEqual(sleeps, [2, 4])

    def test_posts_are_not_repeated(self):
        session = FakeSession().add("POST", r"/group/user$", FakeResponse(503, "unavailable"))
        client = JiraClient("https://example.atlassian.net", session=session, sleep=lambda s: None)
        with self.assertRaises(JiraError) as ctx:
            client.request("POST", "group/user", body={"accountId": "x"}, expected=(201,))
        self.assertEqual(ctx.exception.status, 503)
        self.assertEqual(len(session.calls), 1)

    def test_persistent_outage_gives_up(self):
        session = FakeSession().add("GET", r"/myself$", FakeResponse(504, "gateway timeout"))
        client = JiraClient("https://example.atlassian.net", session=session, max_retries=3, sleep=lambda s: None)
        with self.assertRaises(JiraError):
            client.get("myself")
        self.assertEqual(len(session.calls), 4)


class RateLimitTests(unittest.TestCase):
    def test_retries_after_the_advertised_delay(self):
        limited = FakeResponse(429, {"message": "Rate limit exceeded"}, {"Retry-After": "7"})
        session = FakeSession().add("GET", r"/myself$", Seq(limited, limited, {"accountId": "abc"}))
        sleeps = []
        client = JiraClient("https://example.atlassian.net", session=session, sleep=sleeps.append)
        self.assertEqual(client.get("myself")["accountId"], "abc")
        self.assertEqual(sleeps, [7, 7])
        self.assertEqual(len(session.calls), 3)

    def test_http_date_retry_after(self):
        from datetime import datetime, timezone
        from jiraadmin.client import retry_after
        now = datetime(2023, 12, 10, 12, 0, 0, tzinfo=timezone.utc)
        resp = FakeResponse(429, None, {"Retry-After": "Sun, 10 Dec 2023 12:00:42 GMT"})
        self.assertEqual(retry_after(resp, now=now), 42)
        past = FakeResponse(429, None, {"Retry-After": "Sun, 10 Dec 2023 11:00:00 GMT"})
        self.assertEqual(retry_after(past, now=now), 0)
        junk = FakeResponse(429, None, {"Retry-After": "soon"})
        self.assertEqual(retry_after(junk, now=now), 5)

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
