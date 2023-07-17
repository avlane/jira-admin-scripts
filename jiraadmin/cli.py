"""Command line entry point: python -m jiraadmin <command>."""
import argparse
import sys

from . import config, dashboards, fields, filters, groups, licenses, permissions, report, roles, screens, users, webhooks
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
    p_fields = sub.add_parser("fields", parents=[common], help="custom field audit")
    p_fields.add_argument("--duplicates", action="store_true", help="only fields that share a name and type")
    p_fields.add_argument("--unused", action="store_true", help="fields that look abandoned, ranked by confidence")
    p_fields.add_argument("--stale-days", type=int, default=365, help="age that counts as abandoned (default 365)")
    p_trash = sub.add_parser("trash-fields", parents=[common], help="move abandoned custom fields to the trash")
    p_trash.add_argument("--confidence", choices=("high", "medium", "low"), default="high",
                         help="lowest confidence level to act on (default high)")
    p_trash.add_argument("--stale-days", type=int, default=365)
    p_trash.add_argument("--apply", action="store_true", help="actually trash the fields (default is a dry run)")
    for name, helptext in (("filters", "saved filters that are orphaned or idle"),
                           ("dashboards", "dashboards that are orphaned or idle")):
        p = sub.add_parser(name, parents=[common], help=helptext)
        p.add_argument("--findings-only", action="store_true", help="hide items with nothing to report")
    p_transfer = sub.add_parser("transfer-filters", parents=[common], help="give orphaned filters to another account")
    p_transfer.add_argument("--to", required=True, metavar="ACCOUNT_ID", help="accountId of the new owner")
    p_transfer.add_argument("--min-favourites", type=int, default=1,
                            help="favourites that make an unshared filter worth keeping (default 1)")
    p_transfer.add_argument("--apply", action="store_true", help="make the change (default is a dry run)")
    p_hooks = sub.add_parser("webhooks", parents=[common], help="inventory of admin-registered webhooks")
    p_hooks.add_argument("--internal-domain", action="append", default=[], metavar="DOMAIN",
                         help="domain you control (repeatable); other receivers are flagged as external")
    p_screens = sub.add_parser("screens", parents=[common], help="screens that no screen scheme uses")
    p_screens.add_argument("--schemes", action="store_true", help="report issue type screen schemes and their projects instead")
    return parser


def make_client():
    base, email, token = config.from_env()
    return JiraClient(base, email, token, **config.tuning())


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


def cmd_fields(client, args, out):
    found = fields.custom_fields(client)
    if args.duplicates:
        return emit(fields.duplicate_rows(found), ("name", "type", "ids", "variants"), args, out)
    if args.unused:
        rows = fields.unused_candidates(fields.search_fields(client), stale_days=args.stale_days)
        return emit(rows, ("id", "name", "type", "screens", "confidence", "reason"), args, out)
    rows = [{"id": f["id"], "name": f["name"], "type": fields.field_type(f)} for f in found]
    return emit(rows, ("id", "name", "type"), args, out)


def cmd_trash_fields(client, args, out):
    levels = ("high", "medium", "low")
    wanted = levels[:levels.index(args.confidence) + 1]
    candidates = [c for c in fields.unused_candidates(fields.search_fields(client), stale_days=args.stale_days)
                  if c["confidence"] in wanted]
    if not args.apply:
        out.write("dry run: pass --apply to move these to the trash\n")
    results = fields.trash_fields(client, [c["id"] for c in candidates], apply=args.apply)
    names = {c["id"]: c["name"] for c in candidates}
    rows = [dict(r, name=names[r["id"]]) for r in results]
    emit(rows, ("id", "name", "status", "detail"), args, out)
    return 1 if any(r["status"] == "failed" for r in rows) else 0


def _cleanup_rows(rows, args):
    if args.findings_only:
        rows = [r for r in rows if r["findings"]]
    return rows


def cmd_filters(client, args, out):
    rows = _cleanup_rows(filters.audit(client), args)
    return emit(rows, ("id", "name", "owner", "ownerState", "shared", "favourites", "subscriptions", "findings"), args, out)


def cmd_dashboards(client, args, out):
    rows = _cleanup_rows(dashboards.audit(client), args)
    return emit(rows, ("id", "name", "owner", "ownerState", "shared", "favourites", "findings"), args, out)


def cmd_transfer_filters(client, args, out):
    users.require_assignable(client, args.to)
    plan = filters.transfer_plan(filters.audit(client), args.min_favourites)
    if not args.apply:
        out.write("dry run: pass --apply to make these changes\n")
    chosen = [p["id"] for p in plan if p["action"] == "transfer"]
    done = {r["id"]: r for r in filters.transfer_owner(client, chosen, args.to, apply=args.apply)}
    rows = []
    for item in plan:
        result = done.get(item["id"], {"status": "left", "detail": item["reason"]})
        rows.append(dict(item, status=result["status"], detail=result["detail"] or item["reason"]))
    emit(rows, ("id", "name", "owner", "action", "status", "detail"), args, out)
    return 1 if any(r["status"] == "failed" for r in rows) else 0


def cmd_webhooks(client, args, out):
    rows = webhooks.inventory(client, tuple(args.internal_domain))
    return emit(rows, ("id", "name", "host", "enabled", "events", "filter", "lastUpdatedBy", "lastUpdated", "findings"), args, out)


def cmd_screens(client, args, out):
    if args.schemes:
        rows = screens.issue_type_scheme_report(client)
        return emit(rows, ("id", "name", "projects", "screenSchemes", "unused"), args, out)
    rows = screens.unused_screens(screens.list_screens(client), screens.screen_schemes(client))
    return emit(rows, ("id", "name", "description", "note"), args, out)


HANDLERS = {"users": cmd_users, "inactive": cmd_inactive, "licenses": cmd_licenses,
            "group-members": cmd_group_members, "bulk-groups": cmd_bulk_groups, "roles": cmd_roles,
            "permissions": cmd_permissions, "fields": cmd_fields,
            "trash-fields": cmd_trash_fields, "filters": cmd_filters, "dashboards": cmd_dashboards,
            "transfer-filters": cmd_transfer_filters, "webhooks": cmd_webhooks,
            "screens": cmd_screens}


def main(argv=None, client=None, out=None):
    out = out if out is not None else sys.stdout
    args = build_parser().parse_args(argv)
    try:
        client = client or make_client()
        return HANDLERS[args.command](client, args, out)
    except (config.ConfigError, groups.PlanError, JiraError) as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 2
