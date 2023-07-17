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


def issue_type_screen_schemes(client):
    return list(client.paginate("issuetypescreenscheme", page_size=100))


def scheme_mappings(client):
    return list(client.paginate("issuetypescreenscheme/mapping", page_size=100))


def project_associations(client, project_ids):
    """Which issue type screen scheme each project uses (asks for ids in batches)."""
    found = []
    ids = list(project_ids)
    for start in range(0, len(ids), 50):
        batch = ids[start:start + 50]
        found.extend(client.paginate("issuetypescreenscheme/project", params={"projectId": batch}, page_size=100))
    return found


def issue_type_scheme_report(client):
    """One row per issue type screen scheme: the projects on it and the screen schemes it maps to."""
    from .projects import iter_projects

    projects = {str(p["id"]): p["key"] for p in iter_projects(client)}
    names = {str(s["id"]): s["name"] for s in screen_schemes(client)}
    attached = {}
    for assoc in project_associations(client, projects):
        attached.setdefault(assoc["issueTypeScreenScheme"]["id"], []).extend(
            projects[pid] for pid in assoc["projectIds"] if pid in projects)
    mapped = {}
    for mapping in scheme_mappings(client):
        mapped.setdefault(mapping["issueTypeScreenSchemeId"], set()).add(names.get(str(mapping["screenSchemeId"]), mapping["screenSchemeId"]))
    rows = []
    for scheme in issue_type_screen_schemes(client):
        keys = attached.get(scheme["id"], [])
        rows.append({"id": scheme["id"], "name": scheme["name"], "projects": keys,
                     "screenSchemes": sorted(mapped.get(scheme["id"], [])),
                     "unused": not keys and scheme["id"] != "1"})
    return rows
