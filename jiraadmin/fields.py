"""Custom field audit."""
from datetime import datetime, timedelta, timezone


def custom_fields(client):
    """Every custom field (the endpoint returns system and custom fields together)."""
    return [f for f in client.get("field") if f.get("custom")]


def search_fields(client):
    """Custom fields with screen counts and last-used data, via the paged field search."""
    params = {"type": "custom", "expand": "lastUsed,screensCount"}
    return list(client.paginate("field/search", params=params, page_size=50))


def field_type(field):
    schema = field.get("schema") or {}
    return schema.get("custom", "").rpartition(":")[2] or schema.get("type", "")


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


def _parse(value):
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f%z")


def unused_candidates(fields, now=None, stale_days=365):
    """Fields that look abandoned, with a confidence level.

    high    last value written more than stale_days ago and on no screen
    medium  last value written more than stale_days ago but still on a screen
    low     Jira has no usage data for the field and it is on no screen

    Fields whose usage is not tracked are never reported on that basis alone.
    """
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=stale_days)
    rows = []
    for field in fields:
        last = field.get("lastUsed") or {}
        on_screens = field.get("screensCount")
        confidence, reason = None, ""
        if last.get("type") == "TRACKED" and _parse(last["value"]) < cutoff:
            confidence = "high" if on_screens == 0 else "medium"
            reason = "last used " + last["value"][:10]
        elif last.get("type") == "UNKNOWN" and on_screens == 0:
            confidence, reason = "low", "no usage data, on no screen"
        if confidence:
            rows.append({"id": field["id"], "name": field["name"], "type": field_type(field),
                         "screens": on_screens, "confidence": confidence, "reason": reason})
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(rows, key=lambda r: (order[r["confidence"]], r["id"]))
