"""Shared rules for finding filters and dashboards that need attention."""


def owner_state(owner):
    """'missing' when the owner was deleted, 'inactive' when deactivated, else 'active'."""
    if not owner or not owner.get("accountId"):
        return "missing"
    return "active" if owner.get("active", True) else "inactive"


def findings(owner, shared, favourites, subscriptions=0):
    """List the reasons an item deserves a look.

    orphaned  the owner is gone or deactivated, so nobody can maintain it
    idle      private, never favourited and not subscribed to, so it serves nobody but its owner
    """
    found = []
    if owner_state(owner) != "active":
        found.append("orphaned")
    elif not shared and not favourites and not subscriptions:
        found.append("idle")
    return found
