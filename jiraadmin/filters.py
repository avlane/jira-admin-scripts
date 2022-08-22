"""Saved filter audit."""
from . import cleanup

EXPAND = "owner,jql,favouritedCount,sharePermissions,subscriptions"


def iter_filters(client):
    return client.paginate("filter/search", params={"expand": EXPAND}, page_size=50)


def classify(item):
    owner = item.get("owner")
    subscriptions = (item.get("subscriptions") or {}).get("size", 0)
    return cleanup.findings(owner, bool(item.get("sharePermissions")), item.get("favouritedCount", 0), subscriptions)


def audit(client):
    rows = []
    for item in iter_filters(client):
        owner = item.get("owner") or {}
        rows.append({
            "id": item["id"], "name": item["name"], "owner": owner.get("displayName", "(deleted user)"),
            "ownerId": owner.get("accountId", ""), "ownerState": cleanup.owner_state(owner),
            "shared": bool(item.get("sharePermissions")), "favourites": item.get("favouritedCount", 0),
            "subscriptions": (item.get("subscriptions") or {}).get("size", 0), "findings": classify(item)})
    return rows
