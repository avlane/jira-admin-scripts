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


class TuningTests(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual(config.tuning({}), {"max_retries": 5, "timeout": 30, "min_interval": 0.0})

    def test_overrides(self):
        got = config.tuning({"JIRA_MAX_RETRIES": "2", "JIRA_TIMEOUT": "10"})
        self.assertEqual(got, {"max_retries": 2, "timeout": 10, "min_interval": 0.0})

    def test_requests_per_second_becomes_an_interval(self):
        self.assertEqual(config.tuning({"JIRA_REQUESTS_PER_SECOND": "4"})["min_interval"], 0.25)
        with self.assertRaises(config.ConfigError):
            config.tuning({"JIRA_REQUESTS_PER_SECOND": "0"})
        with self.assertRaises(config.ConfigError):
            config.tuning({"JIRA_REQUESTS_PER_SECOND": "fast"})

    def test_rejects_junk(self):
        with self.assertRaises(config.ConfigError):
            config.tuning({"JIRA_MAX_RETRIES": "lots"})
        with self.assertRaises(config.ConfigError):
            config.tuning({"JIRA_TIMEOUT": "-1"})


if __name__ == "__main__":
    unittest.main()
