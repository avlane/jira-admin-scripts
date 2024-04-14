"""Project role audit: who holds each role in each project."""
from .projects import iter_projects

# Managed by Atlassian apps; empty or app-only by design.
IGNORED_ROLES = ("atlassian-addons-project-access",)


def project_roles(client, project):
    """Map of role name -> role id for one project (the endpoint returns role URLs)."""
    data = client.get("project/{}/role".format(project))
    return {name: int(url.rstrip("/").rsplit("/", 1)[-1]) for name, url in data.items()}


def role_actors(client, project, role_id):
    return client.get("project/{}/role/{}".format(project, role_id)).get("actors", [])


def _actor_row(project, role_name, actor):
    if actor.get("type") == "atlassian-user-role-actor":
        return {"project": project, "role": role_name, "actorType": "user", "actor": actor.get("displayName", ""),
                "actorId": actor.get("actorUser", {}).get("accountId", ""), "finding": "direct-user"}
    group = actor.get("actorGroup", {})
    return {"project": project, "role": role_name, "actorType": "group", "actor": actor.get("displayName", ""),
            "actorId": group.get("groupId", ""), "finding": ""}


def audit(client, projects=None, check_users=False, directory=None):
    """One row per role actor, plus a row for each role nobody holds.

    `projects` is a list of project keys; by default every classic project is checked.
    With check_users, individual users are looked up and deactivated or deleted
    accounts are reported as "inactive-user" instead of "direct-user".
    """
    keys = list(projects) if projects else [p["key"] for p in iter_projects(client)]
    rows = []
    for key in keys:
        for role_name, role_id in sorted(project_roles(client, key).items()):
            if role_name in IGNORED_ROLES:
                continue
            actors = role_actors(client, key, role_id)
            if not actors:
                rows.append({"project": key, "role": role_name, "actorType": "", "actor": "",
                             "actorId": "", "finding": "empty-role"})
            for actor in actors:
                rows.append(_actor_row(key, role_name, actor))
    if check_users:
        from .users import UserDirectory

        directory = directory or UserDirectory(client)
        directory.prefetch(r["actorId"] for r in rows if r["actorType"] == "user")
        for row in rows:
            if row["actorType"] == "user" and not directory.is_active(row["actorId"]):
                row["finding"] = "inactive-user"
    return rows
