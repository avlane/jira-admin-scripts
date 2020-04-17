"""JQL helpers."""


def count_issues(client, jql):
    """Number of issues matching a JQL query, without downloading them."""
    data = client.get("search", params={"jql": jql, "maxResults": 0})
    return data["total"]
