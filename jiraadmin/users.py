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


def inactive_users(client, days=90, limit=None, count=count_issues, exclude=()):
    """Active human accounts that neither hold nor reported an issue touched in `days` days.

    Jira has no "last login" in the REST API, so recent issue involvement is
    the signal. Comments and worklogs on other people's issues are not seen,
    so treat the result as a list of candidates to check, not to deactivate.
    Accounts in `exclude` (service accounts, people on leave) are never searched.
    """
    rows = []
    for user in human_users(client):
        if not user.get("active") or user["accountId"] in exclude:
            continue
        if limit is not None and len(rows) >= limit:
            break
        if count(client, activity_jql(user["accountId"], days)) == 0:
            rows.append({"accountId": user["accountId"], "displayName": user["displayName"],
                         "emailAddress": user.get("emailAddress", ""), "recentIssues": 0})
    return rows


def get_user(client, account_id):
    return client.get("user", params={"accountId": account_id})


def require_assignable(client, account_id):
    """Fetch an account and make sure it can own things: an active Atlassian (human) account."""
    from .client import JiraError

    user = get_user(client, account_id)
    if user.get("accountType") != "atlassian" or not user.get("active"):
        raise JiraError("account {} is not an active user account".format(account_id))
    return user


class UserDirectory:
    """Looks accounts up in batches and remembers the answers for the rest of the run.

    user/bulk silently omits accounts it does not know, so an id that is still
    missing after a lookup is treated as deleted.
    """

    BATCH = 50

    def __init__(self, client):
        self.client = client
        self._users = {}
        self._asked = set()

    def prefetch(self, account_ids):
        wanted = [a for a in dict.fromkeys(account_ids) if a not in self._asked]
        for start in range(0, len(wanted), self.BATCH):
            batch = wanted[start:start + self.BATCH]
            data = self.client.get("user/bulk", params={"accountId": batch, "maxResults": len(batch)})
            for user in data.get("values", []):
                self._users[user["accountId"]] = user
            self._asked.update(batch)

    def get(self, account_id):
        self.prefetch([account_id])
        return self._users.get(account_id)

    def is_active(self, account_id):
        user = self.get(account_id)
        return bool(user and user.get("active"))


def read_account_list(stream):
    """Account ids from a text file: one per line, blank lines and # comments ignored."""
    ids = set()
    for line in stream:
        line = line.split("#", 1)[0].strip()
        if line:
            ids.add(line)
    return ids
