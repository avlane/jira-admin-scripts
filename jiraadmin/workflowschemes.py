"""Workflow scheme report."""
from .projects import iter_projects


def workflow_schemes(client):
    return list(client.paginate("workflowscheme", page_size=50))


def project_schemes(client, project_ids):
    """Map scheme id (or name, for the default scheme which has no id) -> project keys."""
    keys = {str(p["id"]): p["key"] for p in iter_projects(client)}
    ids = [pid for pid in project_ids if pid in keys]
    attached = {}
    for start in range(0, len(ids), 50):
        batch = ids[start:start + 50]
        for item in client.paginate("workflowscheme/project", params={"projectId": batch}, page_size=50):
            scheme = item["workflowScheme"]
            attached.setdefault(scheme.get("id", scheme["name"]), []).extend(keys[pid] for pid in item["projectIds"] if pid in keys)
    return attached


def report(client):
    projects = [str(p["id"]) for p in iter_projects(client)]
    attached = project_schemes(client, projects)
    rows = []
    for scheme in workflow_schemes(client):
        keys = attached.get(scheme.get("id", scheme["name"]), [])
        workflows = {scheme["defaultWorkflow"], *scheme.get("issueTypeMappings", {}).values()}
        rows.append({"id": scheme.get("id", ""), "name": scheme["name"], "defaultWorkflow": scheme["defaultWorkflow"],
                     "workflows": sorted(workflows), "projects": keys, "unused": not keys})
    return rows
