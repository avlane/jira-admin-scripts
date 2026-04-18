import os
import tempfile
import unittest

from jiraadmin import config

TOML = """
[profiles.prod]
url = "https://example.atlassian.net"
email = "ops@example.com"
token_env = "JIRA_PROD_TOKEN"

[profiles.sandbox]
url = "https://example-sandbox.atlassian.net/"
email = "ops@example.com"
"""


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "jiraadmin.toml")
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(TOML)

    def test_profile_with_its_own_token_variable(self):
        got = config.from_profile(self.path, "prod", {"JIRA_PROD_TOKEN": "tok-prod"})
        self.assertEqual(got, ("https://example.atlassian.net", "ops@example.com", "tok-prod"))

    def test_default_token_variable(self):
        got = config.from_profile(self.path, "sandbox", {"JIRA_API_TOKEN": "tok"})
        self.assertEqual(got, ("https://example-sandbox.atlassian.net", "ops@example.com", "tok"))

    def test_missing_token_names_the_variable(self):
        with self.assertRaises(config.ConfigError) as ctx:
            config.from_profile(self.path, "prod", {})
        self.assertIn("$JIRA_PROD_TOKEN", str(ctx.exception))

    def test_unknown_profile_lists_the_known_ones(self):
        with self.assertRaises(config.ConfigError) as ctx:
            config.from_profile(self.path, "staging", {})
        self.assertIn("prod, sandbox", str(ctx.exception))

    def test_missing_and_broken_files(self):
        with self.assertRaises(config.ConfigError):
            config.from_profile(os.path.join(self.tmp.name, "nope.toml"), "prod", {})
        broken = os.path.join(self.tmp.name, "broken.toml")
        with open(broken, "w", encoding="utf-8") as handle:
            handle.write("[profiles.prod\nurl = ")
        with self.assertRaises(config.ConfigError):
            config.from_profile(broken, "prod", {})


if __name__ == "__main__":
    unittest.main()
