"""User listing and audits."""


def iter_users(client, page_size=100):
    """Every account Jira knows about, including deactivated ones."""
    return client.paginate("users/search", page_size=page_size)


def human_users(client):
    """Atlassian accounts only.

    users/search also returns app accounts (bots, integrations) and customer
    accounts (service desk portal users); neither takes a licence seat the way
    staff do, so audits skip them.
    """
    return [u for u in iter_users(client) if u.get("accountType") == "atlassian"]
