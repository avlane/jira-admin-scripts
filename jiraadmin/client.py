"""Minimal Jira Cloud REST client (basic auth with an API token)."""
import logging
import math
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Iterator, Optional


class JiraError(Exception):
    def __init__(self, message, status=None, url=None):
        super().__init__(message)
        self.status = status
        self.url = url


log = logging.getLogger("jiraadmin.client")

# Gateway errors Atlassian returns during short outages. Only requests that are
# safe to repeat are retried; a POST that timed out may already have happened.
TRANSIENT = (502, 503, 504)
IDEMPOTENT = ("GET", "PUT", "DELETE")

HINTS = {
    401: "check JIRA_EMAIL and JIRA_API_TOKEN; API tokens expire (after at most a year), so you may need a new one",
    403: "the account is not allowed to do this; most admin commands need the Administer Jira permission",
}


def default_session(email, token):
    import requests  # imported lazily so the tests run without it installed

    session = requests.Session()
    session.auth = (email, token)
    session.headers.update({"Accept": "application/json", "User-Agent": "jira-admin-scripts/0.1"})
    return session


def seconds_until(stamp, now=None):
    """Seconds from now until an ISO 8601 timestamp such as 2025-07-13T10:00:05Z, or None if unparsable."""
    if not stamp:
        return None
    try:
        when = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    return max(0, math.ceil((when - now).total_seconds()))


def retry_after(resp, default: int = 5, now: Optional[datetime] = None) -> int:
    """Seconds to wait before retrying a 429, from the Retry-After header.

    The header is either a number of seconds or an HTTP date.
    """
    value = resp.headers.get("Retry-After")
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        pass
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return default
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    return max(0, math.ceil((when - now).total_seconds()))


class JiraClient:
    API = "/rest/api/3/"

    def __init__(self, base_url, email=None, token=None, session=None, timeout=30,
                 max_retries=5, sleep=time.sleep, min_interval=0.0, clock=time.monotonic):
        self.base_url = base_url.rstrip("/")
        self.session = session if session is not None else default_session(email, token)
        self.timeout = timeout
        self.max_retries = max_retries
        self.sleep = sleep
        self.min_interval = min_interval
        self.clock = clock
        self._last_request = None

    def _pace(self):
        """Keep at least min_interval seconds between requests."""
        if self.min_interval and self._last_request is not None:
            wait = self._last_request + self.min_interval - self.clock()
            if wait > 0:
                self.sleep(wait)
        self._last_request = self.clock()

    def _ease_off(self, resp):
        """Pause when Jira says the rate limit budget is nearly spent, before a 429 happens.

        Atlassian is rolling out X-RateLimit-* headers; when they are absent this does nothing.
        """
        if str(resp.headers.get("X-RateLimit-NearLimit", "")).lower() != "true":
            return
        delay = seconds_until(resp.headers.get("X-RateLimit-Reset"))
        delay = min(1 if delay is None else delay, 10)
        if delay:
            log.info("close to the rate limit (remaining %s); pausing %ss", resp.headers.get("X-RateLimit-Remaining", "?"), delay)
            self.sleep(delay)

    def url(self, path: str) -> str:
        if path.startswith("/rest/"):
            return self.base_url + path
        return self.base_url + self.API + path.lstrip("/")

    def request(self, method, path, params=None, body=None, expected=(200,)):
        url = self.url(path)
        attempt = 0
        while True:
            log.debug("%s %s", method, url)
            self._pace()
            resp = self.session.request(method, url, params=params, json=body, timeout=self.timeout)
            if resp.status_code == 429 and attempt < self.max_retries:
                attempt += 1
                delay = retry_after(resp)
                log.warning("rate limited on %s %s (%s); waiting %ss (retry %d of %d)", method, url,
                            resp.headers.get("RateLimit-Reason", "no reason given"), delay, attempt, self.max_retries)
                self.sleep(delay)
                continue
            if resp.status_code in TRANSIENT and method.upper() in IDEMPOTENT and attempt < self.max_retries:
                attempt += 1
                delay = min(2 ** attempt, 30)
                log.warning("HTTP %s on %s %s; retrying in %ss (retry %d of %d)", resp.status_code, method, url, delay, attempt, self.max_retries)
                self.sleep(delay)
                continue
            break
        self._ease_off(resp)
        if resp.status_code not in expected:
            message = "{} {} failed with HTTP {}: {}".format(method, url, resp.status_code, resp.text[:200])
            if resp.status_code in HINTS:
                message += " ({})".format(HINTS[resp.status_code])
            raise JiraError(message, resp.status_code, url)
        if resp.status_code == 204 or not resp.text:
            return None
        return resp.json()

    def get(self, path: str, params: Optional[dict] = None) -> Any:
        return self.request("GET", path, params=params)

    def paginate(self, path: str, params: Optional[dict] = None, key: str = "values",
                 page_size: int = 50) -> Iterator[dict]:
        """Yield every item from a startAt/maxResults endpoint.

        Handles both the paged shape ({"values": [...], "isLast": ...}) and
        endpoints that return a bare JSON array.
        """
        start = 0
        while True:
            query = dict(params or {})
            query.update({"startAt": start, "maxResults": page_size})
            data = self.get(path, query)
            items = data if isinstance(data, list) else data.get(key, [])
            for item in items:
                yield item
            if not items:
                return
            if isinstance(data, dict):
                if data.get("isLast") is True:
                    return
                total = data.get("total")
                if total is not None and start + len(items) >= total:
                    return
            # Jira may return fewer items than asked for (it caps some endpoints
            # below the requested maxResults), so a short bare array is not the
            # end; keep going until an empty page.
            start += len(items)
