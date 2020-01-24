"""Test helpers: a fake HTTP session that replays recorded JSON fixtures."""
import json as jsonlib
import os
import re

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def load(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return jsonlib.load(f)


class FakeResponse:
    def __init__(self, status_code=200, body=None, headers=None):
        self.status_code = status_code
        self._body = body
        self.headers = headers or {}
        if body is None:
            self.text = ""
        elif isinstance(body, str):
            self.text = body
        else:
            self.text = jsonlib.dumps(body)
        self.content = self.text.encode("utf-8")

    @property
    def ok(self):
        return self.status_code < 400

    def json(self):
        if self._body is None or isinstance(self._body, str):
            raise ValueError("response has no JSON body")
        return self._body

    def iter_content(self, chunk_size=8192):
        for i in range(0, len(self.content), chunk_size):
            yield self.content[i:i + chunk_size]


class Seq:
    """Responses handed out in order; the last one repeats."""

    def __init__(self, *items):
        self.items = list(items)

    def next(self):
        if len(self.items) > 1:
            return self.items.pop(0)
        return self.items[0]


class FakeSession:
    def __init__(self):
        self.routes = []
        self.calls = []
        self.auth = None
        self.headers = {}

    def add(self, method, pattern, response):
        """response: a JSON body, a FakeResponse, a Seq, or a callable(call) returning either."""
        self.routes.append((method.upper(), re.compile(pattern), response))
        return self

    def request(self, method, url, params=None, json=None, headers=None, timeout=None,
                data=None, stream=False, allow_redirects=True, **kwargs):
        call = {"method": method.upper(), "url": url, "params": dict(params or {}),
                "json": json, "data": data}
        self.calls.append(call)
        for m, rx, resp in self.routes:
            if m == call["method"] and rx.search(url):
                if isinstance(resp, Seq):
                    resp = resp.next()
                if callable(resp):
                    resp = resp(call)
                if isinstance(resp, FakeResponse):
                    return resp
                return FakeResponse(200, resp)
        raise AssertionError("no fake route for {} {} {}".format(method, url, params))

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def calls_to(self, method, pattern):
        rx = re.compile(pattern)
        return [c for c in self.calls if c["method"] == method.upper() and rx.search(c["url"])]


def paged(items, key=None, cap=None, total=True, last_flag=True):
    """Build a route handler that serves `items` using startAt/maxResults paging.

    key=None serves bare JSON arrays (like users/search); otherwise a PageBean under `key`.
    cap lowers the page size, the way Jira does when a client asks for too much.
    """
    def handler(call):
        start = int(call["params"].get("startAt", 0))
        size = int(call["params"].get("maxResults", 50))
        if cap:
            size = min(size, cap)
        page = items[start:start + size]
        if key is None:
            return page
        body = {"startAt": start, "maxResults": size, key: page}
        if total:
            body["total"] = len(items)
        if last_flag:
            body["isLast"] = start + len(page) >= len(items)
        return body
    return handler
