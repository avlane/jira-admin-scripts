"""Group membership lookups."""


def members(client, group, include_inactive=False):
    """All members of a group, by name. Page size is capped at 50 by Jira."""
    params = {"groupname": group, "includeInactiveUsers": "true" if include_inactive else "false"}
    return list(client.paginate("group/member", params=params, page_size=50))


class PlanError(ValueError):
    pass


def read_plan(stream):
    """Parse a CSV with the columns action, group, accountId into a list of steps."""
    import csv

    reader = csv.DictReader(stream)
    missing = {"action", "group", "accountId"} - set(reader.fieldnames or [])
    if missing:
        raise PlanError("CSV is missing column(s): " + ", ".join(sorted(missing)))
    steps = []
    for number, row in enumerate(reader, start=2):
        action = (row["action"] or "").strip().lower()
        if action not in ("add", "remove"):
            raise PlanError("line {}: unsupported action {!r}".format(number, action))
        group = (row["group"] or "").strip()
        account_id = (row["accountId"] or "").strip()
        if not group or not account_id:
            raise PlanError("line {}: group and accountId are required".format(number))
        steps.append({"action": action, "group": group, "accountId": account_id})
    return steps


def _result(step, status, detail=""):
    return dict(step, status=status, detail=detail)


def run_plan(client, steps, apply=False):
    """Execute (or, by default, just describe) the steps. Returns one result per step."""
    from .client import JiraError

    current = {}
    results = []
    for step in steps:
        group, account_id = step["group"], step["accountId"]
        if group not in current:
            current[group] = {m["accountId"] for m in members(client, group, include_inactive=True)}
        adding = step["action"] == "add"
        is_member = account_id in current[group]
        if adding == is_member:
            results.append(_result(step, "skipped", "already a member" if adding else "not a member"))
            continue
        if not apply:
            results.append(_result(step, "planned", "would add" if adding else "would remove"))
            continue
        try:
            if adding:
                client.request("POST", "group/user", params={"groupname": group},
                               body={"accountId": account_id}, expected=(200, 201))
            else:
                client.request("DELETE", "group/user", params={"groupname": group, "accountId": account_id},
                               expected=(200, 204))
        except JiraError as exc:
            results.append(_result(step, "failed", str(exc)))
            continue
        if adding:
            current[group].add(account_id)
        else:
            current[group].discard(account_id)
        results.append(_result(step, "added" if adding else "removed"))
    return results
