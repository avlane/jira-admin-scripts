"""Licence seat usage from the application roles endpoint."""


def application_roles(client):
    return client.get("applicationrole")


def summarize(roles, warn_at=90):
    """One row per application with seat usage; `warning` is set at or above warn_at percent."""
    rows = []
    for role in roles:
        seats = role.get("numberOfSeats")
        used = role.get("userCount", 0)
        unlimited = bool(role.get("hasUnlimitedSeats"))
        percent = None
        if seats and not unlimited:
            percent = round(100.0 * used / seats, 1)
        rows.append({
            "key": role["key"],
            "name": role.get("name", role["key"]),
            "seats": "unlimited" if unlimited else seats,
            "used": used,
            "remaining": role.get("remainingSeats"),
            "percent": percent,
            "warning": percent is not None and percent >= warn_at,
        })
    return rows
