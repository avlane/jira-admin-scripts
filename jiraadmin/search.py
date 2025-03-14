"""JQL helpers on the enhanced search endpoint (search/jql).

Unlike the old search resource it pages with an opaque nextPageToken, has no
startAt and no total, so counting means walking the results.
"""


def iter_issues(client, jql, fields=("key",), page_size=100, max_pages=500):
    """Yield issues matching a JQL query, following nextPageToken until it runs out.

    max_pages is a safety stop: a query that matches millions of issues should
    fail loudly rather than run for hours.
    """
    params = {"jql": jql, "maxResults": page_size, "fields": ",".join(fields)}
    pages = 0
    while True:
        pages += 1
        if pages > max_pages:
            raise RuntimeError("search stopped after {} pages; narrow the JQL".format(max_pages))
        data = client.get("search/jql", params=params)
        for issue in data.get("issues", []):
            yield issue
        token = data.get("nextPageToken")
        if not token or data.get("isLast"):
            return
        params = dict(params, nextPageToken=token)


def count_issues(client, jql, limit=None):
    """Number of issues matching a JQL query; with limit, stops as soon as that many are seen."""
    page_size = 100 if limit is None else max(1, min(limit, 100))
    seen = 0
    for _ in iter_issues(client, jql, fields=("id",), page_size=page_size):
        seen += 1
        if limit is not None and seen >= limit:
            break
    return seen


def approximate_count(client, jql):
    """Estimated number of matching issues from one POST, without paging through them.

    Good enough for "roughly how many", not for deciding that the answer is zero.
    """
    return client.request("POST", "search/approximate-count", body={"jql": jql}, expected=(200,))["count"]
