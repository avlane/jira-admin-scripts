"""Read connection settings from environment variables."""
import os

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


def _rate(env: dict[str, str]) -> float:
    raw = env.get("JIRA_REQUESTS_PER_SECOND")
    if raw in (None, ""):
        return 0.0
    try:
        value = float(raw)
    except ValueError:
        raise ConfigError("JIRA_REQUESTS_PER_SECOND must be a number (got {!r})".format(raw))
    if value <= 0:
        raise ConfigError("JIRA_REQUESTS_PER_SECOND must be greater than zero")
    return 1.0 / value


def tuning(environ: dict[str, str] | None = None) -> dict:
    """Optional knobs: JIRA_MAX_RETRIES, JIRA_TIMEOUT (seconds) and JIRA_REQUESTS_PER_SECOND."""
    env = os.environ if environ is None else environ
    return {"max_retries": _int(env, "JIRA_MAX_RETRIES", 5), "timeout": _int(env, "JIRA_TIMEOUT", 30),
            "min_interval": _rate(env), "max_wait": _int(env, "JIRA_MAX_WAIT", 300)}


DEFAULT_CONFIG = "~/.config/jiraadmin.toml"


def load_profile(path: str, name: str) -> dict:
    """Read [profiles.<name>] from a TOML file.

    A profile holds `url`, `email` and `token_env`, the *name* of the environment
    variable that holds the API token. Tokens are never read from the file itself.
    """
    try:
        import tomllib
    except ImportError:
        raise ConfigError("config files need Python 3.11 or newer (tomllib); use environment variables instead")
    path = os.path.expanduser(path)
    try:
        with open(path, "rb") as handle:
            data = tomllib.load(handle)
    except FileNotFoundError:
        raise ConfigError("config file not found: " + path)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError("{}: {}".format(path, exc))
    profiles = data.get("profiles", {})
    if name not in profiles:
        raise ConfigError("no profile {!r} in {} (found: {})".format(name, path, ", ".join(sorted(profiles)) or "none"))
    return profiles[name]


def from_profile(path: str, name: str, environ: dict[str, str] | None = None) -> tuple[str, str, str]:
    """Return (base_url, email, token) for a named profile."""
    env = os.environ if environ is None else environ
    profile = load_profile(path, name)
    token_env = profile.get("token_env", TOKEN_VAR)
    if not env.get(token_env):
        raise ConfigError("profile {!r} expects the API token in ${}".format(name, token_env))
    return from_env({URL_VAR: profile.get("url", ""), EMAIL_VAR: profile.get("email", ""), TOKEN_VAR: env[token_env]})


def from_env(environ: dict[str, str] | None = None) -> tuple[str, str, str]:
    """Return (base_url, email, token) or raise ConfigError naming what is missing."""
    env = os.environ if environ is None else environ
    missing = [name for name in (URL_VAR, EMAIL_VAR, TOKEN_VAR) if not env.get(name)]
    if missing:
        raise ConfigError("missing environment variable(s): " + ", ".join(missing))
    base = env[URL_VAR].strip().rstrip("/")
    if not base.startswith("https://"):
        raise ConfigError("{} must start with https:// (got {!r})".format(URL_VAR, base))
    return base, env[EMAIL_VAR].strip(), env[TOKEN_VAR].strip()
