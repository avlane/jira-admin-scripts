"""Workflow report: which workflows no workflow scheme uses."""
from . import workflowschemes


def list_workflows(client):
    params = {"expand": "schemes,statuses"}
    return list(client.paginate("workflow/search", params=params, page_size=50))


def report(client):
    """One row per workflow, flagged when no scheme, or only unused schemes, point at it."""
    dead_schemes = {str(s["id"]) for s in workflowschemes.report(client) if s["unused"]}
    rows = []
    for flow in list_workflows(client):
        schemes = [s["id"] for s in flow.get("schemes", [])]
        finding = ""
        if flow.get("isDefault"):
            finding = ""
        elif not schemes:
            finding = "unused"
        elif all(s in dead_schemes for s in schemes):
            finding = "only-in-unused-schemes"
        rows.append({"name": flow["id"]["name"], "entityId": flow["id"].get("entityId", ""),
                     "statuses": len(flow.get("statuses", [])), "schemes": len(schemes),
                     "default": bool(flow.get("isDefault")), "finding": finding})
    return rows
