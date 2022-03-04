"""Custom field audit."""


def custom_fields(client):
    """Every custom field (the endpoint returns system and custom fields together)."""
    return [f for f in client.get("field") if f.get("custom")]


def field_type(field):
    return (field.get("schema") or {}).get("custom", "").rpartition(":")[2] or (field.get("schema") or {}).get("type", "")


def duplicates(fields):
    """Groups of custom fields that share a name (ignoring case) and a field type.

    These are usually the same idea created twice, often by two teams, and the
    reason a screen offers "Story Points" and "Story points" side by side.
    """
    groups = {}
    for field in fields:
        key = (field["name"].strip().casefold(), (field.get("schema") or {}).get("custom", ""))
        groups.setdefault(key, []).append(field)
    return [members for members in groups.values() if len(members) > 1]


def duplicate_rows(fields):
    rows = []
    for members in duplicates(fields):
        rows.append({"name": members[0]["name"], "type": field_type(members[0]),
                     "ids": [m["id"] for m in members], "variants": sorted({m["name"] for m in members})})
    return rows


def usage(client, fields, count=None):
    """Issue count per custom field, using `cf[id] is not EMPTY`.

    Slow: one search per field. Fields the search index cannot query (some app
    fields) come back with a count of None rather than failing the run.
    """
    from .client import JiraError
    from .search import count_issues

    count = count or count_issues
    rows = []
    for field in fields:
        custom_id = field["schema"]["customId"]
        try:
            issues = count(client, "cf[{}] is not EMPTY".format(custom_id))
        except JiraError as exc:
            if exc.status != 400:
                raise
            issues = None
        rows.append({"id": field["id"], "name": field["name"], "type": field_type(field), "issues": issues})
    return rows


def unused(rows):
    return [r for r in rows if r["issues"] == 0]
