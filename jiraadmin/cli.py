"""Command line entry point: python -m jiraadmin <command>."""
import argparse
import logging
import os
import sys
from datetime import datetime, timezone

from . import (config, dashboards, doctor, fields, filters, groups, licenses, permissions, progress, projects, report, roles,
               screens, search, users, webhooks, workflows, workflowschemes)
from .client import JiraClient, JiraError

FORMATS = ("table", "csv", "json", "markdown")
COMMANDS = {}


def command(name, summary, arguments=None):
    """Register a subcommand. `arguments(parser)` adds its options; the decorated function runs it."""
    def register(func):
        COMMANDS[name] = {"run": func, "summary": summary, "arguments": arguments}
        return func
    return register


def _apply_flag(parser):
    parser.add_argument("--apply", action="store_true", help="make the changes (default is a dry run)")


def _findings_only(parser):
    parser.add_argument("--findings-only", action="store_true", help="hide items with nothing to report")


def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--format", choices=FORMATS, default="table", help="output format (default table)")
    common.add_argument("--profile", metavar="NAME", help="use [profiles.NAME] from the config file instead of JIRA_* variables")
    common.add_argument("--config", metavar="FILE", help="profile file (default {})".format(config.DEFAULT_CONFIG))
    common.add_argument("--output-dir", metavar="DIR", help="also save the rows as a timestamped JSON file in DIR")
    common.add_argument("--progress", action="store_true", help="show progress on stderr during long audits")
    common.add_argument("-v", "--verbose", action="count", default=0,
                        help="log requests and rate-limit waits to stderr (-vv for debug)")
    parser = argparse.ArgumentParser(
        prog="jiraadmin",
        description="Jira Cloud admin helpers. Read-only unless a command says otherwise.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, spec in COMMANDS.items():
        sub_parser = sub.add_parser(name, parents=[common], help=spec["summary"])
        if spec["arguments"]:
            spec["arguments"](sub_parser)
    return parser


def make_client(args=None):
    profile = getattr(args, "profile", None)
    if profile:
        base, email, token = config.from_profile(args.config or config.DEFAULT_CONFIG, profile)
    else:
        base, email, token = config.from_env()
    return JiraClient(base, email, token, **config.tuning())


def utcnow():
    return datetime.now(timezone.utc)


def save_copy(rows, columns, args):
    """Write the rows as JSON to <output-dir>/<command>-<UTC timestamp>.json and return the path."""
    os.makedirs(args.output_dir, exist_ok=True)
    stamp = utcnow().strftime("%Y%m%dT%H%M%SZ")
    base = os.path.join(args.output_dir, "{}-{}".format(args.command, stamp))
    path, number = base + ".json", 1
    while True:
        try:
            handle = open(path, "x", encoding="utf-8")
        except FileExistsError:
            number += 1
            path = "{}-{}.json".format(base, number)
            continue
        break
    with handle:
        handle.write(report.render(rows, columns, "json"))
    print("saved {}".format(path), file=sys.stderr)
    return path


def emit(rows, columns, args, out):
    out.write(report.render(rows, columns, args.format))
    if args.output_dir:
        save_copy(rows, columns, args)
    return 0


def dry_run_notice(args, out, what="make these changes"):
    """Notices go to stderr so --format json and csv output stays machine readable."""
    if not args.apply:
        print("dry run: pass --apply to {}".format(what), file=sys.stderr)


def failed(rows):
    return 1 if any(r["status"] == "failed" for r in rows) else 0


def _users_args(p):
    p.add_argument("--inactive-only", action="store_true", help="only deactivated accounts")


@command("users", "list Atlassian user accounts", _users_args)
def cmd_users(client, args, out):
    rows = []
    for user in users.human_users(client):
        if args.inactive_only and user.get("active"):
            continue
        rows.append({"accountId": user["accountId"], "status": "active" if user.get("active") else "inactive",
                     "displayName": user.get("displayName", ""), "emailAddress": user.get("emailAddress", "")})
    return emit(rows, ("accountId", "status", "displayName", "emailAddress"), args, out)


def _inactive_args(p):
    p.add_argument("--days", type=int, default=90, help="look-back window (default 90)")
    p.add_argument("--limit", type=int, help="stop after this many candidates")
    p.add_argument("--exclude-file", metavar="FILE", help="accountIds to skip, one per line")


@command("inactive", "active accounts with no recent issue activity", _inactive_args)
def cmd_inactive(client, args, out):
    exclude = ()
    if args.exclude_file:
        with open(args.exclude_file, encoding="utf-8") as handle:
            exclude = users.read_account_list(handle)
    tracker = progress.Progress("inactive", enabled=args.progress)
    rows = users.inactive_users(client, days=args.days, limit=args.limit, exclude=exclude, progress=tracker)
    tracker.finish()
    return emit(rows, ("accountId", "displayName", "emailAddress", "recentIssues"), args, out)


def _licenses_args(p):
    p.add_argument("--warn-at", type=int, default=90, help="flag applications at or above this percent")


@command("licenses", "licence seat usage per application", _licenses_args)
def cmd_licenses(client, args, out):
    rows = licenses.summarize(licenses.application_roles(client), args.warn_at)
    return emit(rows, ("key", "name", "seats", "used", "remaining", "percent", "warning"), args, out)


def _members_args(p):
    p.add_argument("group", nargs="?", help="group name")
    p.add_argument("--group-id", help="look the group up by groupId instead of name")
    p.add_argument("--include-inactive", action="store_true")


@command("group-members", "list the members of a group", _members_args)
def cmd_group_members(client, args, out):
    if bool(args.group) == bool(args.group_id):
        print("error: give a group name or --group-id", file=sys.stderr)
        return 2
    rows = [{"accountId": u["accountId"], "displayName": u.get("displayName", ""), "active": u.get("active")}
            for u in groups.members(client, args.group, args.include_inactive, args.group_id)]
    return emit(rows, ("accountId", "displayName", "active"), args, out)


def _bulk_args(p):
    p.add_argument("csv_file", help="CSV with columns action, group, accountId")
    _apply_flag(p)


@command("bulk-groups", "add or remove group members from a CSV file", _bulk_args)
def cmd_bulk_groups(client, args, out):
    with open(args.csv_file, newline="", encoding="utf-8") as handle:
        steps = groups.read_plan(handle)
    results = groups.run_plan(client, steps, apply=args.apply, directory=users.UserDirectory(client))
    dry_run_notice(args, out)
    emit(results, ("action", "group", "groupId", "accountId", "status", "detail"), args, out)
    counts = groups.summarize(results)
    print("summary: " + (", ".join("{} {}".format(n, s) for s, n in sorted(counts.items())) or "nothing to do"), file=sys.stderr)
    return failed(results)


def _roles_args(p):
    p.add_argument("--project", action="append", help="project key (repeatable); default is all classic projects")
    p.add_argument("--findings-only", action="store_true", help="hide rows without a finding")
    p.add_argument("--check-users", action="store_true", help="look up individual users and flag deactivated ones")


@command("roles", "who holds each project role", _roles_args)
def cmd_roles(client, args, out):
    tracker = progress.Progress("roles", every=5, enabled=args.progress)
    rows = roles.audit(client, projects=args.project, check_users=args.check_users, progress=tracker)
    tracker.finish()
    if args.findings_only:
        rows = [r for r in rows if r["finding"]]
    return emit(rows, ("project", "role", "actorType", "actor", "finding"), args, out)


def _permissions_args(p):
    p.add_argument("--grants", action="store_true", help="list risky grants instead of the scheme summary")
    p.add_argument("--duplicates", action="store_true", help="list schemes that grant exactly the same things")


@command("permissions", "permission schemes and the projects that use them", _permissions_args)
def cmd_permissions(client, args, out):
    if args.duplicates:
        rows = [{"schemes": [s["name"] for s in group], "ids": [s["id"] for s in group]}
                for group in permissions.duplicate_schemes(permissions.schemes(client))]
        return emit(rows, ("schemes", "ids"), args, out)
    if args.grants:
        return emit(permissions.grant_report(client), ("scheme", "permission", "holder", "finding"), args, out)
    return emit(permissions.scheme_summary(client), ("id", "name", "grants", "projects", "unused"), args, out)


def _fields_args(p):
    p.add_argument("--duplicates", action="store_true", help="only fields that share a name and type")
    p.add_argument("--unused", action="store_true", help="fields that look abandoned, ranked by confidence")
    p.add_argument("--stale-days", type=int, default=365, help="age that counts as abandoned (default 365)")


@command("fields", "custom field audit", _fields_args)
def cmd_fields(client, args, out):
    found = fields.custom_fields(client)
    if args.duplicates:
        return emit(fields.duplicate_rows(found), ("name", "type", "ids", "variants"), args, out)
    if args.unused:
        rows = fields.unused_candidates(fields.search_fields(client), stale_days=args.stale_days)
        return emit(rows, ("id", "name", "type", "screens", "confidence", "reason"), args, out)
    rows = [{"id": f["id"], "name": f["name"], "type": fields.field_type(f)} for f in found]
    return emit(rows, ("id", "name", "type"), args, out)


def _trash_args(p):
    p.add_argument("--confidence", choices=("high", "medium", "low"), default="high",
                   help="lowest confidence level to act on (default high)")
    p.add_argument("--stale-days", type=int, default=365)
    _apply_flag(p)


@command("trash-fields", "move abandoned custom fields to the trash", _trash_args)
def cmd_trash_fields(client, args, out):
    levels = ("high", "medium", "low")
    wanted = levels[:levels.index(args.confidence) + 1]
    candidates = [c for c in fields.unused_candidates(fields.search_fields(client), stale_days=args.stale_days)
                  if c["confidence"] in wanted]
    dry_run_notice(args, out, "move these to the trash")
    results = fields.trash_fields(client, [c["id"] for c in candidates], apply=args.apply)
    names = {c["id"]: c["name"] for c in candidates}
    rows = [dict(r, name=names[r["id"]]) for r in results]
    emit(rows, ("id", "name", "status", "detail"), args, out)
    return failed(rows)


def _cleanup_rows(rows, args):
    if args.findings_only:
        rows = [r for r in rows if r["findings"]]
    return rows


@command("filters", "saved filters that are orphaned or idle", _findings_only)
def cmd_filters(client, args, out):
    rows = _cleanup_rows(filters.audit(client), args)
    return emit(rows, ("id", "name", "owner", "ownerState", "shared", "favourites", "subscriptions", "findings"), args, out)


@command("dashboards", "dashboards that are orphaned or idle", _findings_only)
def cmd_dashboards(client, args, out):
    rows = _cleanup_rows(dashboards.audit(client), args)
    return emit(rows, ("id", "name", "owner", "ownerState", "shared", "favourites", "findings"), args, out)


def _transfer_args(p):
    p.add_argument("--to", required=True, metavar="ACCOUNT_ID", help="accountId of the new owner")
    p.add_argument("--min-favourites", type=int, default=1,
                   help="favourites that make an unshared filter worth keeping (default 1)")
    _apply_flag(p)


@command("transfer-filters", "give orphaned filters to another account", _transfer_args)
def cmd_transfer_filters(client, args, out):
    users.require_assignable(client, args.to)
    plan = filters.transfer_plan(filters.audit(client), args.min_favourites)
    dry_run_notice(args, out)
    chosen = [p["id"] for p in plan if p["action"] == "transfer"]
    done = {r["id"]: r for r in filters.transfer_owner(client, chosen, args.to, apply=args.apply)}
    rows = []
    for item in plan:
        result = done.get(item["id"], {"status": "left", "detail": item["reason"]})
        rows.append(dict(item, status=result["status"], detail=result["detail"] or item["reason"]))
    emit(rows, ("id", "name", "owner", "action", "status", "detail"), args, out)
    return failed(rows)


def _transfer_dashboards_args(p):
    p.add_argument("--to", required=True, metavar="ACCOUNT_ID", help="accountId of the new owner")
    _apply_flag(p)


@command("transfer-dashboards", "give orphaned dashboards to another account", _transfer_dashboards_args)
def cmd_transfer_dashboards(client, args, out):
    users.require_assignable(client, args.to)
    orphaned = [r for r in dashboards.audit(client) if "orphaned" in r["findings"]]
    dry_run_notice(args, out)
    results = dashboards.change_owner(client, [r["id"] for r in orphaned], args.to, apply=args.apply)
    names = {r["id"]: r for r in orphaned}
    rows = [dict(r, name=names[r["id"]]["name"], owner=names[r["id"]]["owner"]) for r in results]
    emit(rows, ("id", "name", "owner", "status", "detail"), args, out)
    return failed(rows)


def _webhooks_args(p):
    p.add_argument("--internal-domain", action="append", default=[], metavar="DOMAIN",
                   help="domain you control (repeatable); other receivers are flagged as external")


@command("webhooks", "inventory of admin-registered webhooks", _webhooks_args)
def cmd_webhooks(client, args, out):
    rows = webhooks.inventory(client, tuple(args.internal_domain))
    return emit(rows, ("id", "name", "host", "enabled", "events", "filter", "lastUpdatedBy", "lastUpdated", "findings"), args, out)


def _screens_args(p):
    p.add_argument("--schemes", action="store_true", help="report issue type screen schemes and their projects instead")


@command("screens", "screens that no screen scheme uses", _screens_args)
def cmd_screens(client, args, out):
    if args.schemes:
        rows = screens.issue_type_scheme_report(client)
        return emit(rows, ("id", "name", "projects", "screenSchemes", "unused"), args, out)
    rows = screens.unused_screens(screens.list_screens(client), screens.screen_schemes(client))
    return emit(rows, ("id", "name", "description", "note"), args, out)


def setup_logging(verbosity):
    level = logging.WARNING if verbosity == 0 else logging.INFO if verbosity == 1 else logging.DEBUG
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s", stream=sys.stderr)


@command("workflow-schemes", "workflow schemes and the projects that use them")
def cmd_workflow_schemes(client, args, out):
    rows = workflowschemes.report(client)
    return emit(rows, ("id", "name", "defaultWorkflow", "workflows", "projects", "unused"), args, out)


def _workflows_args(p):
    p.add_argument("--findings-only", action="store_true", help="only workflows nothing uses")


@command("workflows", "workflows that no workflow scheme uses", _workflows_args)
def cmd_workflows(client, args, out):
    rows = workflows.report(client)
    if args.findings_only:
        rows = [r for r in rows if r["finding"]]
    return emit(rows, ("name", "statuses", "schemes", "default", "finding"), args, out)


def _projects_args(p):
    p.add_argument("--stale-days", type=int, default=365, help="idle time that counts as stale (default 365)")
    p.add_argument("--findings-only", action="store_true", help="only stale and empty projects")


@command("projects", "projects with no recent issue activity", _projects_args)
def cmd_projects(client, args, out):
    tracker = progress.Progress("projects", every=5, enabled=args.progress)
    rows = projects.stale_report(client, days=args.stale_days, progress=tracker)
    tracker.finish()
    if args.findings_only:
        rows = [r for r in rows if r["finding"]]
    return emit(rows, ("key", "name", "lead", "leadActive", "lastUpdated", "idleDays", "finding"), args, out)


def _archive_args(p):
    p.add_argument("--stale-days", type=int, default=365)
    p.add_argument("--include-stale", action="store_true", help="also archive stale projects, not just empty ones")
    _apply_flag(p)


@command("archive-projects", "archive empty (and optionally stale) projects", _archive_args)
def cmd_archive_projects(client, args, out):
    wanted = ("empty", "stale") if args.include_stale else ("empty",)
    chosen = [r["key"] for r in projects.stale_report(client, days=args.stale_days) if r["finding"] in wanted]
    dry_run_notice(args, out, "archive these projects")
    rows = projects.archive_projects(client, chosen, apply=args.apply)
    emit(rows, ("key", "status", "detail"), args, out)
    return failed(rows)


@command("empty-groups", "groups that have no members")
def cmd_empty_groups(client, args, out):
    return emit(groups.empty_groups(client), ("name", "groupId", "members"), args, out)


@command("doctor", "check credentials and permissions before a long audit")
def cmd_doctor(client, args, out):
    rows = doctor.run_checks(client)
    emit(rows, ("check", "status", "detail"), args, out)
    return 1 if any(r["status"] == "fail" for r in rows) else 0


def _count_args(p):
    p.add_argument("jql", help="JQL query to count")
    p.add_argument("--exact", action="store_true", help="page through every match instead of asking for an estimate")


@command("count", "how many issues match a JQL query", _count_args)
def cmd_count(client, args, out):
    if args.exact:
        number = search.count_issues(client, args.jql)
    else:
        number = search.approximate_count(client, args.jql)
    return emit([{"jql": args.jql, "count": number, "exact": args.exact}], ("jql", "count", "exact"), args, out)


def main(argv=None, client=None, out=None):
    out = out if out is not None else sys.stdout
    args = build_parser().parse_args(argv)
    setup_logging(args.verbose)
    try:
        client = client or make_client(args)
        return COMMANDS[args.command]["run"](client, args, out)
    except (config.ConfigError, groups.PlanError, JiraError) as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 2
