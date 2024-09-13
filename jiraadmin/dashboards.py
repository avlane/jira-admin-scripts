"""Dashboard audit."""
from . import cleanup

EXPAND = "owner,sharePermissions"


def iter_dashboards(client):
    return client.paginate("dashboard/search", params={"expand": EXPAND}, page_size=50)


def classify(item):
    # "popularity" is how many people have favourited the dashboard.
    return cleanup.findings(item.get("owner"), bool(item.get("sharePermissions")), item.get("popularity", 0))


def audit(client):
    rows = []
    for item in iter_dashboards(client):
        owner = item.get("owner") or {}
        rows.append({
            "id": item["id"], "name": item["name"], "owner": owner.get("displayName", "(deleted user)"),
            "ownerId": owner.get("accountId", ""), "ownerState": cleanup.owner_state(owner),
            "shared": bool(item.get("sharePermissions")), "favourites": item.get("popularity", 0),
            "findings": classify(item)})
    return rows


def change_owner(client, dashboard_ids, new_owner, apply=False):
    """Move dashboards to another owner in one bulk-edit request. Dry run unless apply is set.

    Uses PUT dashboard/bulk/edit with the changeOwner action and admin
    permissions extended, so it works on dashboards the caller cannot see.
    """
    from .client import JiraError

    ids = [str(i) for i in dashboard_ids]
    if not ids:
        return []
    if not apply:
        return [{"id": i, "status": "planned", "detail": "would transfer"} for i in ids]
    body = {"action": "changeOwner", "entityIds": [int(i) for i in ids], "extendAdminPermissions": True,
            "changeOwnerDetails": {"autofixName": True, "newOwner": new_owner}}
    try:
        client.request("PUT", "dashboard/bulk/edit", body=body, expected=(200, 204))
    except JiraError as exc:
        return [{"id": i, "status": "failed", "detail": str(exc)} for i in ids]
    return [{"id": i, "status": "transferred", "detail": ""} for i in ids]
