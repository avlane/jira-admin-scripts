"""Connectivity and permission checks to run before a long audit."""
from .client import JiraError


def run_checks(client):
    """Return rows of {check, status, detail}; status is ok or fail."""
    rows = []

    def record(check, ok, detail):
        rows.append({"check": check, "status": "ok" if ok else "fail", "detail": detail})

    try:
        info = client.get("serverInfo")
    except JiraError as exc:
        record("site", False, str(exc))
        return rows
    if info.get("deploymentType") == "Cloud":
        record("site", True, "{} (Cloud, version {})".format(info.get("serverTitle", "?"), info.get("version", "?")))
    else:
        record("site", False, "{} is a {} deployment; these scripts target Jira Cloud".format(
            client.base_url, info.get("deploymentType", "unknown")))
        return rows
    try:
        me = client.get("myself")
    except JiraError as exc:
        record("authentication", False, str(exc))
        return rows
    record("authentication", True, "{} ({})".format(me.get("displayName", "?"), me.get("accountId", "?")))
    try:
        perm = client.get("mypermissions", params={"permissions": "ADMINISTER"})["permissions"].get("ADMINISTER", {})
    except JiraError as exc:
        record("administer jira", False, str(exc))
    else:
        record("administer jira", bool(perm.get("havePermission")),
               "granted" if perm.get("havePermission") else "missing; read-only audits will mostly work, changes will not")
    return rows
