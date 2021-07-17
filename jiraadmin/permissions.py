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


def scheme_summary(client):
    usage = scheme_usage(client)
    rows = []
    for scheme in schemes(client):
        projects = usage.get(scheme["id"], [])
        rows.append({"id": scheme["id"], "name": scheme["name"], "grants": len(scheme.get("permissions", [])),
                     "projects": len(projects), "projectKeys": projects, "unused": not projects})
    return rows
