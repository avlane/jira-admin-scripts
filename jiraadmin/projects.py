"""Project listing."""


def iter_projects(client, include_team_managed=False):
    """Yield projects visible to the caller.

    Team-managed projects (reported as `simplified`) have their own role and
    permission model that the classic scheme endpoints do not describe, so
    they are left out unless asked for.
    """
    for project in client.paginate("project/search", page_size=50):
        if project.get("simplified") and not include_team_managed:
            continue
        yield project
