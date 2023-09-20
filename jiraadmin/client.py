"""Minimal Jira Cloud REST client (basic auth with an API token)."""
import logging
import time
from typing import Any, Iterator, Optional


class JiraError(Exception):
    def __init__(self, message, status=None, url=None):
        super().__init__(message)
        self.status = status
        self.url = url


log = logging.getLogger("jiraadmin.client")


def default_session(email, token):
    import requests  # imported lazily so the tests run without it installed

    session = requests.Session()
    session.auth = (email, token)
    session.headers.update({"Accept": "application/json", "User-Agent": "jira-admin-scripts/0.1"})
    return session


def retry_after(resp, default: int = 5) -> int:
    """Seconds to wait before retrying a 429, from the Retry-After header."""
    value = resp.headers.get("Retry-After")
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


class JiraClient:
    API = "/rest/api/3/"

    def __init__(self, base_url, email=None, token=None, session=None, timeout=30,
                 max_retries=5, sleep=time.sleep):
        self.base_url = base_url.rstrip("/")
        self.session = session if session is not None else default_session(email, token)
        self.timeout = timeout
        self.max_retries = max_retries
        self.sleep = sleep

    def url(self, path: str) -> str:
        if path.startswith("/rest/"):
            return self.base_url + path
        return self.base_url + self.API + path.lstrip("/")

    def request(self, method, path, params=None, body=None, expected=(200,)):
        url = self.url(path)
        attempt = 0
        while True:
            log.debug("%s %s", method, url)
            resp = self.session.request(method, url, params=params, json=body, timeout=self.timeout)
            if resp.status_code == 429 and attempt < self.max_retries:
                attempt += 1
                delay = retry_after(resp)
                log.warning("rate limited on %s %s; waiting %ss (retry %d of %d)", method, url, delay, attempt, self.max_retries)
                self.sleep(delay)
                continue
            break
        if resp.status_code not in expected:
            raise JiraError("{} {} failed with HTTP {}: {}".format(method, url, resp.status_code, resp.text[:200]),
                            resp.status_code, url)
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
