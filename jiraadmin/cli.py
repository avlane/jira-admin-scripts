"""Command line entry point: python -m jiraadmin <command>."""
import argparse
import sys

from . import config, groups, licenses, permissions, report, roles, users
from .client import JiraClient, JiraError

FORMATS = ("table", "csv", "json")


def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--format", choices=FORMATS, default="table", help="output format (default table)")
    parser = argparse.ArgumentParser(
        prog="jiraadmin",
        description="Jira Cloud admin helpers. Read-only unless a command says otherwise.")
    sub = parser.add_subparsers(dest="command", required=True)
    p_users = sub.add_parser("users", parents=[common], help="list Atlassian user accounts")
    p_users.add_argument("--inactive-only", action="store_true", help="only deactivated accounts")
    p_inactive = sub.add_parser("inactive", parents=[common], help="active accounts with no recent issue activity")
    p_inactive.add_argument("--days", type=int, default=90, help="look-back window (default 90)")
    p_inactive.add_argument("--limit", type=int, help="stop after this many candidates")
    p_lic = sub.add_parser("licenses", parents=[common], help="licence seat usage per application")
    p_lic.add_argument("--warn-at", type=int, default=90, help="flag applications at or above this percent")
    p_members = sub.add_parser("group-members", parents=[common], help="list the members of a group")
    p_members.add_argument("group", nargs="?", help="group name")
    p_members.add_argument("--group-id", help="look the group up by groupId instead of name")
    p_members.add_argument("--include-inactive", action="store_true")
    p_bulk = sub.add_parser("bulk-groups", parents=[common], help="add users to groups from a CSV file")
    p_bulk.add_argument("csv_file", help="CSV with columns action, group, accountId")
    p_bulk.add_argument("--apply", action="store_true", help="make the changes (default is a dry run)")
    p_roles = sub.add_parser("roles", parents=[common], help="who holds each project role")
    p_roles.add_argument("--project", action="append", help="project key (repeatable); default is all classic projects")
    p_roles.add_argument("--findings-only", action="store_true", help="hide rows without a finding")
    p_perm = sub.add_parser("permissions", parents=[common], help="permission schemes and the projects that use them")
    p_perm.add_argument("--grants", action="store_true", help="list risky grants instead of the scheme summary")
    return parser


def make_client():
    base, email, token = config.from_env()
    return JiraClient(base, email, token)


def emit(rows, columns, args, out):
    out.write(report.render(rows, columns, args.format))
    return 0


def cmd_users(client, args, out):
    rows = []
    for user in users.human_users(client):
        if args.inactive_only and user.get("active"):
            continue
        rows.append({"accountId": user["accountId"], "status": "active" if user.get("active") else "inactive",
                     "displayName": user.get("displayName", ""), "emailAddress": user.get("emailAddress", "")})
    return emit(rows, ("accountId", "status", "displayName", "emailAddress"), args, out)


def cmd_inactive(client, args, out):
    rows = users.inactive_users(client, days=args.days, limit=args.limit)
    return emit(rows, ("accountId", "displayName", "emailAddress", "recentIssues"), args, out)


def cmd_licenses(client, args, out):
    rows = licenses.summarize(licenses.application_roles(client), args.warn_at)
    return emit(rows, ("key", "name", "seats", "used", "remaining", "percent", "warning"), args, out)


def cmd_group_members(client, args, out):
    if bool(args.group) == bool(args.group_id):
        print("error: give a group name or --group-id", file=sys.stderr)
        return 2
    rows = [{"accountId": u["accountId"], "displayName": u.get("displayName", ""), "active": u.get("active")}
            for u in groups.members(client, args.group, args.include_inactive, args.group_id)]
    return emit(rows, ("accountId", "displayName", "active"), args, out)


def cmd_bulk_groups(client, args, out):
    with open(args.csv_file, newline="", encoding="utf-8") as handle:
        steps = groups.read_plan(handle)
    results = groups.run_plan(client, steps, apply=args.apply)
    if not args.apply:
        out.write("dry run: pass --apply to make these changes\n")
    emit(results, ("action", "group", "accountId", "status", "detail"), args, out)
    return 1 if any(r["status"] == "failed" for r in results) else 0


def cmd_roles(client, args, out):
    rows = roles.audit(client, projects=args.project)
    if args.findings_only:
        rows = [r for r in rows if r["finding"]]
    return emit(rows, ("project", "role", "actorType", "actor", "finding"), args, out)


def cmd_permissions(client, args, out):
    if args.grants:
        return emit(permissions.grant_report(client), ("scheme", "permission", "holder", "finding"), args, out)
    return emit(permissions.scheme_summary(client), ("id", "name", "grants", "projects", "unused"), args, out)


HANDLERS = {"users": cmd_users, "inactive": cmd_inactive, "licenses": cmd_licenses,
            "group-members": cmd_group_members, "bulk-groups": cmd_bulk_groups, "roles": cmd_roles,
            "permissions": cmd_permissions}


def main(argv=None, client=None, out=None):
    out = out if out is not None else sys.stdout
    args = build_parser().parse_args(argv)
    try:
        client = client or make_client()
        return HANDLERS[args.command](client, args, out)
    except (config.ConfigError, groups.PlanError, JiraError) as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 2
