"""User listing and audits."""
from .search import count_issues


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


def activity_jql(account_id, days):
    return '(assignee = "{0}" OR reporter = "{0}") AND updated >= -{1}d'.format(account_id, days)


def inactive_users(client, days=90, limit=None, count=count_issues):
    """Active human accounts that neither hold nor reported an issue touched in `days` days.

    Jira has no "last login" in the REST API, so recent issue involvement is
    the signal. Comments and worklogs on other people's issues are not seen,
    so treat the result as a list of candidates to check, not to deactivate.
    """
    rows = []
    for user in human_users(client):
        if not user.get("active"):
            continue
        if limit is not None and len(rows) >= limit:
            break
        if count(client, activity_jql(user["accountId"], days)) == 0:
            rows.append({"accountId": user["accountId"], "displayName": user["displayName"],
                         "emailAddress": user["emailAddress"], "recentIssues": 0})
    return rows
