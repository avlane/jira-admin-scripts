"""Minimal Jira Cloud REST client (basic auth with an API token)."""


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


class JiraClient:
    API = "/rest/api/3/"

    def __init__(self, base_url, email=None, token=None, session=None, timeout=30):
        self.base_url = base_url.rstrip("/")
        self.session = session if session is not None else default_session(email, token)
        self.timeout = timeout

    def url(self, path):
        if path.startswith("/rest/"):
            return self.base_url + path
        return self.base_url + self.API + path.lstrip("/")

    def request(self, method, path, params=None, body=None, expected=(200,)):
        url = self.url(path)
        resp = self.session.request(method, url, params=params, json=body, timeout=self.timeout)
        if resp.status_code not in expected:
            raise JiraError("{} {} failed with HTTP {}: {}".format(method, url, resp.status_code, resp.text[:200]),
                            resp.status_code, url)
        if resp.status_code == 204 or not resp.text:
            return None
        return resp.json()

    def get(self, path, params=None):
        return self.request("GET", path, params=params)
