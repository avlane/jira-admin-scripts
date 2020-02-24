"""Minimal Jira Cloud REST client (basic auth with an API token)."""
import time


class JiraError(Exception):
    def __init__(self, message, status=None, url=None):
        super().__init__(message)
        self.status = status
        self.url = url


def default_session(email, token):
    import requests  # imported lazily so the tests run without it installed

    session = requests.Session()
    session.auth = (email, token)
    session.headers.update({"Accept": "application/json", "User-Agent": "jira-admin-scripts/0.1"})
    return session


def retry_after(resp, default=5):
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

    def url(self, path):
        if path.startswith("/rest/"):
            return self.base_url + path
        return self.base_url + self.API + path.lstrip("/")

    def request(self, method, path, params=None, body=None, expected=(200,)):
        url = self.url(path)
        attempt = 0
        while True:
            resp = self.session.request(method, url, params=params, json=body, timeout=self.timeout)
            if resp.status_code == 429 and attempt < self.max_retries:
                attempt += 1
                self.sleep(retry_after(resp))
                continue
            break
        if resp.status_code not in expected:
            raise JiraError("{} {} failed with HTTP {}: {}".format(method, url, resp.status_code, resp.text[:200]),
                            resp.status_code, url)
        if resp.status_code == 204 or not resp.text:
            return None
        return resp.json()

    def get(self, path, params=None):
        return self.request("GET", path, params=params)

    def paginate(self, path, params=None, key="values", page_size=50):
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
            elif len(items) < page_size:
                return
            start += len(items)
