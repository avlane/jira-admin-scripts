"""Group membership lookups."""


def members(client, group, include_inactive=False):
    """All members of a group, by name. Page size is capped at 50 by Jira."""
    params = {"groupname": group, "includeInactiveUsers": "true" if include_inactive else "false"}
    return list(client.paginate("group/member", params=params, page_size=50))
