"""Screen and screen scheme reports."""


def list_screens(client):
    return list(client.paginate("screens", page_size=100))


def screen_schemes(client):
    return list(client.paginate("screenscheme", page_size=100))


def referenced_screen_ids(schemes):
    """Ids of every screen that some screen scheme points at (default/create/edit/view)."""
    return {screen_id for scheme in schemes for screen_id in scheme.get("screens", {}).values()}


def unused_screens(screens, schemes):
    """Screens that no screen scheme uses.

    Screens can also be attached to workflow transitions, which this does not
    inspect, so check a screen's "Used in" list in the admin UI before deleting it.
    """
    used = referenced_screen_ids(schemes)
    return [{"id": s["id"], "name": s["name"], "description": s.get("description", ""),
             "note": "in no screen scheme; may still be a workflow transition screen"}
            for s in screens if s["id"] not in used]
