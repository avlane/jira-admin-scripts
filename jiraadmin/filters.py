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


def transfer_plan(rows, min_favourites=1):
    """Decide what to do with each orphaned filter row from audit().

    Filters that anybody still relies on (shared, favourited, or subscribed to)
    are worth keeping; the rest are better deleted than inherited.
    """
    plan = []
    for row in rows:
        if "orphaned" not in row["findings"]:
            continue
        in_use = row["shared"] or row["favourites"] >= min_favourites or row["subscriptions"] > 0
        plan.append({"id": row["id"], "name": row["name"], "owner": row["owner"],
                     "action": "transfer" if in_use else "leave",
                     "reason": "still in use" if in_use else "unused; consider deleting"})
    return plan


def transfer_owner(client, filter_ids, new_owner, apply=False):
    """Hand filters to another account. Dry run unless apply is set.

    Uses PUT filter/{id}/owner, which needs the Administer Jira global permission.
    """
    from .client import JiraError

    results = []
    for filter_id in filter_ids:
        if not apply:
            results.append({"id": filter_id, "status": "planned", "detail": "would transfer"})
            continue
        try:
            client.request("PUT", "filter/{}/owner".format(filter_id), body={"accountId": new_owner}, expected=(200, 204))
        except JiraError as exc:
            results.append({"id": filter_id, "status": "failed", "detail": str(exc)})
            continue
        results.append({"id": filter_id, "status": "transferred", "detail": ""})
    return results
