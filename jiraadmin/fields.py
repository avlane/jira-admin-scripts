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
