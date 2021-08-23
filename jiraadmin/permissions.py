"""Permission scheme reporting."""
from .projects import iter_projects


def schemes(client):
    """All permission schemes with their grants."""
    return client.get("permissionscheme", params={"expand": "permissions"})["permissionSchemes"]


def project_scheme_id(client, project_key):
    return client.get("project/{}/permissionscheme".format(project_key))["id"]


def scheme_usage(client):
    """Map scheme id -> list of project keys that use it (classic projects only)."""
    usage = {}
    for project in iter_projects(client):
        usage.setdefault(project_scheme_id(client, project["key"]), []).append(project["key"])
    return usage


RISKY = {"ADMINISTER_PROJECTS", "DELETE_ISSUES", "DELETE_ALL_COMMENTS", "DELETE_ALL_ATTACHMENTS",
         "DELETE_ALL_WORKLOGS", "EDIT_ALL_WORKLOGS", "MANAGE_WATCHERS", "MODIFY_REPORTER"}
WRITE = {"CREATE_ISSUES", "EDIT_ISSUES", "TRANSITION_ISSUES", "ASSIGN_ISSUES", "ADD_COMMENTS"}


def holder_label(holder):
    kind = holder.get("type", "")
    if kind in ("anyone", "applicationRole") and not holder.get("parameter"):
        return kind
    return "{}:{}".format(kind, holder.get("parameter", ""))


def grant_findings(scheme):
    """Yield (permission, holder, finding) for grants worth a second look.

    anyone            the permission is open to people who are not logged in
    direct-user       granted to one account instead of a group or role
    broad-risky       a destructive permission held by every licensed user
    """
    for grant in scheme.get("permissions", []):
        holder, permission = grant.get("holder", {}), grant.get("permission", "")
        kind = holder.get("type")
        if kind == "anyone" and (permission in RISKY or permission in WRITE):
            yield permission, holder_label(holder), "anyone"
        elif kind == "user":
            yield permission, holder_label(holder), "direct-user"
        elif kind == "applicationRole" and not holder.get("parameter") and permission in RISKY:
            yield permission, holder_label(holder), "broad-risky"


def grant_report(client):
    rows = []
    for scheme in schemes(client):
        for permission, holder, finding in grant_findings(scheme):
            rows.append({"scheme": scheme["name"], "permission": permission, "holder": holder, "finding": finding})
    return rows


def scheme_summary(client):
    usage = scheme_usage(client)
    rows = []
    for scheme in schemes(client):
        projects = usage.get(scheme["id"], [])
        rows.append({"id": scheme["id"], "name": scheme["name"], "grants": len(scheme.get("permissions", [])),
                     "projects": len(projects), "projectKeys": projects, "unused": not projects})
    return rows
