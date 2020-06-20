"""Command line entry point: python -m jiraadmin <command>."""
import argparse
import sys

from . import config, licenses, report, users
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


HANDLERS = {"users": cmd_users, "inactive": cmd_inactive, "licenses": cmd_licenses}


def main(argv=None, client=None, out=None):
    out = out if out is not None else sys.stdout
    args = build_parser().parse_args(argv)
    try:
        client = client or make_client()
        return HANDLERS[args.command](client, args, out)
    except (config.ConfigError, JiraError) as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 2
