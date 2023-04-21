import unittest

from jiraadmin import webhooks
from jiraadmin.client import JiraClient
from tests.helpers import FakeSession, load


def make_client():
    session = FakeSession().add("GET", r"/rest/webhooks/1.0/webhook$", load("webhooks.json"))
    return JiraClient("https://example.atlassian.net", session=session), session


class WebhookTests(unittest.TestCase):
    def test_inventory_rows(self):
        client, session = make_client()
        rows = webhooks.inventory(client)
        self.assertEqual([r["name"] for r in rows], ["Deploy notifier", "Old Slack bridge", "Partner audit sink"])
        self.assertEqual(rows[0]["host"], "ci.example.com")
        self.assertEqual(rows[0]["filter"], "project = PLAT")
        self.assertEqual(rows[0]["lastUpdated"], "2022-03-01")
        self.assertEqual(rows[2]["id"], "3")
        self.assertTrue(session.calls[0]["url"].endswith("/rest/webhooks/1.0/webhook"))

    def test_host_never_includes_the_token(self):
        client, _ = make_client()
        self.assertNotIn("s3cr3t", str(webhooks.inventory(client)))

    def test_findings(self):
        client, _ = make_client()
        rows = {r["name"]: r["findings"] for r in webhooks.inventory(client, internal_domains=("example.com",))}
        self.assertEqual(rows["Deploy notifier"], ["secret-in-url"])
        self.assertEqual(rows["Old Slack bridge"], ["disabled", "plain-http", "no-filter", "external"])
        self.assertEqual(rows["Partner audit sink"], ["no-filter", "external"])

    def test_without_internal_domains_nothing_is_external(self):
        client, _ = make_client()
        self.assertTrue(all("external" not in r["findings"] for r in webhooks.inventory(client)))

    def test_subdomains_count_as_internal(self):
        hook = {"url": "https://ci.build.example.com/x", "enabled": True, "filters": {"a": "b"}}
        self.assertEqual(webhooks.findings(hook, ("example.com",)), [])
        self.assertEqual(webhooks.findings(dict(hook, url="https://notexample.com/x"), ("example.com",)), ["external"])

    def test_no_webhooks(self):
        session = FakeSession().add("GET", r"/webhook$", [])
        self.assertEqual(webhooks.inventory(JiraClient("https://example.atlassian.net", session=session)), [])


if __name__ == "__main__":
    unittest.main()
