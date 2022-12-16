"""Read connection settings from environment variables."""
import os
from typing import Optional

URL_VAR = "JIRA_URL"
EMAIL_VAR = "JIRA_EMAIL"
TOKEN_VAR = "JIRA_API_TOKEN"


class ConfigError(Exception):
    pass


def _int(env: dict[str, str], name: str, default: int) -> int:
    raw = env.get(name)
    if raw in (None, ""):
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError("{} must be a whole number (got {!r})".format(name, raw))
    if value < 0:
        raise ConfigError("{} must not be negative".format(name))
    return value


def tuning(environ: Optional[dict[str, str]] = None) -> dict[str, int]:
    """Optional knobs: JIRA_MAX_RETRIES for 429 handling and JIRA_TIMEOUT in seconds."""
    env = os.environ if environ is None else environ
    return {"max_retries": _int(env, "JIRA_MAX_RETRIES", 5), "timeout": _int(env, "JIRA_TIMEOUT", 30)}


def from_env(environ: Optional[dict[str, str]] = None) -> tuple[str, str, str]:
    """Return (base_url, email, token) or raise ConfigError naming what is missing."""
    env = os.environ if environ is None else environ
    missing = [name for name in (URL_VAR, EMAIL_VAR, TOKEN_VAR) if not env.get(name)]
    if missing:
        raise ConfigError("missing environment variable(s): " + ", ".join(missing))
    base = env[URL_VAR].strip().rstrip("/")
    if not base.startswith("https://"):
        raise ConfigError("{} must start with https:// (got {!r})".format(URL_VAR, base))
    return base, env[EMAIL_VAR].strip(), env[TOKEN_VAR].strip()
