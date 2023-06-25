"""Screen and screen scheme reports."""


def list_screens(client):
    return list(client.paginate("screens", page_size=100))


def screen_schemes(client):
    return list(client.paginate("screenscheme", page_size=100))


def referenced_screen_ids(schemes):
    """Ids of every screen that some screen scheme points at (default/create/edit/view)."""
    return {screen_id for scheme in schemes for screen_id in scheme.get("screens", {}).values()}


def unused_screen_schemes(schemes):
    """Screen schemes that no issue type screen scheme uses."""
    return [s for s in schemes if not s.get("issueTypeScreenSchemes", {}).get("values")]


def unused_screens(screens, schemes):
    """Screens that no screen scheme in use points at.

    A screen used only by a screen scheme that no issue type screen scheme
    uses is just as dead. Screens can also be attached to workflow transitions,
    which this does not inspect, so check a screen's "Used in" list in the
    admin UI before deleting it.
    """
    dead = {s["id"] for s in unused_screen_schemes(schemes)}
    live = referenced_screen_ids([s for s in schemes if s["id"] not in dead])
    dead_only = referenced_screen_ids(s for s in schemes if s["id"] in dead) - live
    rows = []
    for screen in screens:
        if screen["id"] in live:
            continue
        note = "in no screen scheme" if screen["id"] not in dead_only else "only in a screen scheme nothing uses"
        rows.append({"id": screen["id"], "name": screen["name"], "description": screen.get("description", ""),
                     "note": note + "; may still be a workflow transition screen"})
    return rows
