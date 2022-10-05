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
