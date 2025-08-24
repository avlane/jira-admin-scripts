"""Project listing."""


def iter_projects(client, include_team_managed=False, expand=None):
    """Yield projects visible to the caller.

    Team-managed projects (reported as `simplified`) have their own role and
    permission model that the classic scheme endpoints do not describe, so
    they are left out unless asked for.
    """
    params = {"expand": expand} if expand else None
    for project in client.paginate("project/search", params=params, page_size=50):
        if project.get("simplified") and not include_team_managed:
            continue
        yield project


def _parse(value):
    from datetime import datetime

    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f%z")


def last_updated(client, key):
    """Timestamp of the most recently updated issue in a project, or None if it has no issues."""
    from .search import iter_issues

    jql = 'project = "{}" ORDER BY updated DESC'.format(key)
    for issue in iter_issues(client, jql, fields=("updated",), page_size=1):
        return issue["fields"]["updated"]
    return None


def stale_report(client, days=365, now=None, progress=None):
    """Classic projects with no issue activity for `days` days, or no issues at all."""
    from datetime import datetime, timezone

    now = now or datetime.now(timezone.utc)
    rows = []
    for project in iter_projects(client, expand="lead"):
        if progress is not None:
            progress.tick()
        updated = last_updated(client, project["key"])
        idle = (now - _parse(updated)).days if updated else None
        finding = "empty" if updated is None else "stale" if idle >= days else ""
        lead = project.get("lead") or {}
        rows.append({"key": project["key"], "name": project["name"], "lead": lead.get("displayName", ""),
                     "leadActive": lead.get("active"), "lastUpdated": updated[:10] if updated else "",
                     "idleDays": idle, "finding": finding})
    return rows


def archive_projects(client, keys, apply=False):
    """Archive projects. Dry run unless apply is set. Archived projects can be restored from the admin UI."""
    from .actions import run_each

    return run_each(keys, lambda key: client.request("POST", "project/{}/archive".format(key), expected=(200, 202, 204)),
                    apply=apply, key="key", planned="would archive", done="archived")
