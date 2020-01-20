import unittest

from jiraadmin import config


GOOD = {"JIRA_URL": "https://example.atlassian.net/", "JIRA_EMAIL": " ops@example.com ", "JIRA_API_TOKEN": "tok"}


class ConfigTests(unittest.TestCase):
    def test_reads_and_normalises(self):
        base, email, token = config.from_env(GOOD)
        self.assertEqual(base, "https://example.atlassian.net")
        self.assertEqual(email, "ops@example.com")
        self.assertEqual(token, "tok")

    def test_names_every_missing_variable(self):
        with self.assertRaises(config.ConfigError) as ctx:
            config.from_env({"JIRA_URL": "https://example.atlassian.net"})
        self.assertIn("JIRA_EMAIL", str(ctx.exception))
        self.assertIn("JIRA_API_TOKEN", str(ctx.exception))

    def test_rejects_plain_http(self):
        env = dict(GOOD, JIRA_URL="http://example.atlassian.net")
        with self.assertRaises(config.ConfigError):
            config.from_env(env)


if __name__ == "__main__":
    unittest.main()
