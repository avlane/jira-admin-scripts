"""Read connection settings from environment variables."""
import os

URL_VAR = "JIRA_URL"
EMAIL_VAR = "JIRA_EMAIL"
TOKEN_VAR = "JIRA_API_TOKEN"


class ConfigError(Exception):
    pass


def from_env(environ=None):
    """Return (base_url, email, token) or raise ConfigError naming what is missing."""
    env = os.environ if environ is None else environ
    missing = [name for name in (URL_VAR, EMAIL_VAR, TOKEN_VAR) if not env.get(name)]
    if missing:
        raise ConfigError("missing environment variable(s): " + ", ".join(missing))
    base = env[URL_VAR].strip().rstrip("/")
    if not base.startswith("https://"):
        raise ConfigError("{} must start with https:// (got {!r})".format(URL_VAR, base))
    return base, env[EMAIL_VAR].strip(), env[TOKEN_VAR].strip()
