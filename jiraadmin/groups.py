"""Group membership lookups."""


def members(client, group=None, include_inactive=False, group_id=None):
    """All members of a group, by name or by groupId. Page size is capped at 50 by Jira.

    Group names can change and are no longer guaranteed unique, so groupId is
    the stable way to refer to a group when you have it.
    """
    if bool(group) == bool(group_id):
        raise ValueError("give exactly one of group or group_id")
    params = {"includeInactiveUsers": "true" if include_inactive else "false"}
    params["groupId" if group_id else "groupname"] = group_id or group
    return list(client.paginate("group/member", params=params, page_size=50))


class PlanError(ValueError):
    pass


def read_plan(stream):
    """Parse a CSV into a list of steps.

    Columns: action, accountId, and group (a name) or groupId. When a row has
    both, the groupId is used.
    """
    import csv

    reader = csv.DictReader(stream)
    names = set(reader.fieldnames or [])
    missing = {"action", "accountId"} - names
    if not names & {"group", "groupId"}:
        missing.add("group (or groupId)")
    if missing:
        raise PlanError("CSV is missing column(s): " + ", ".join(sorted(missing)))
    steps = []
    seen = {}
    for number, row in enumerate(reader, start=2):
        action = (row["action"] or "").strip().lower()
        if action not in ("add", "remove"):
            raise PlanError("line {}: unsupported action {!r}".format(number, action))
        group = (row.get("group") or "").strip()
        group_id = (row.get("groupId") or "").strip()
        account_id = (row["accountId"] or "").strip()
        if not (group or group_id) or not account_id:
            raise PlanError("line {}: a group (or groupId) and an accountId are required".format(number))
        ref = group_id or group
        earlier = seen.get((ref, account_id))
        if earlier is None:
            seen[(ref, account_id)] = action
        elif earlier != action:
            raise PlanError("line {}: {} is both added to and removed from {}".format(number, account_id, ref))
        else:
            continue  # exact duplicate row; keep the first
        step = {"action": action, "group": group, "accountId": account_id}
        if group_id:
            step["groupId"] = group_id
        steps.append(step)
    return steps


def _group_params(step):
    if step.get("groupId"):
        return {"groupId": step["groupId"]}
    return {"groupname": step["group"]}


def summarize(results):
    """Count results by status, e.g. {"added": 3, "skipped": 1}."""
    counts = {}
    for result in results:
        counts[result["status"]] = counts.get(result["status"], 0) + 1
    return counts


def _result(step, status, detail=""):
    return dict(step, status=status, detail=detail)


def run_plan(client, steps, apply=False, directory=None):
    """Execute (or, by default, just describe) the steps. Returns one result per step.

    When a UserDirectory is given, accounts to be added are checked first and
    unknown or deactivated ones fail without a request being made.
    """
    from .client import JiraError

    if directory is not None:
        directory.prefetch(s["accountId"] for s in steps if s["action"] == "add")

    current = {}
    results = []
    for step in steps:
        group, account_id = step.get("groupId") or step["group"], step["accountId"]
        if group not in current:
            found = members(client, None if step.get("groupId") else group, include_inactive=True, group_id=step.get("groupId"))
            current[group] = {m["accountId"] for m in found}
        adding = step["action"] == "add"
        if adding and directory is not None and not directory.is_active(account_id):
            results.append(_result(step, "failed", "unknown or deactivated account"))
            continue
        is_member = account_id in current[group]
        if adding == is_member:
            results.append(_result(step, "skipped", "already a member" if adding else "not a member"))
            continue
        if not apply:
            results.append(_result(step, "planned", "would add" if adding else "would remove"))
            continue
        try:
            if adding:
                client.request("POST", "group/user", params=_group_params(step),
                               body={"accountId": account_id}, expected=(200, 201))
            else:
                client.request("DELETE", "group/user", params=dict(_group_params(step), accountId=account_id),
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


def iter_groups(client):
    """Every group, via group/bulk (name and groupId)."""
    return client.paginate("group/bulk", page_size=100)


def empty_groups(client):
    """Groups with no members at all, active or not."""
    rows = []
    for group in iter_groups(client):
        if member_count(client, group["groupId"]) == 0:
            rows.append({"name": group["name"], "groupId": group["groupId"], "members": 0})
    return rows


def member_count(client, group_id):
    """Total members of a group from one request: ask for a single member and read `total`."""
    params = {"groupId": group_id, "includeInactiveUsers": "true", "maxResults": 1}
    return client.get("group/member", params=params).get("total", 0)
