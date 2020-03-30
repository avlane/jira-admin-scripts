"""Command line entry point: python -m jiraadmin <command>."""
import argparse
import sys

from . import config, users
from .client import JiraClient, JiraError


def build_parser():
    parser = argparse.ArgumentParser(
        prog="jiraadmin",
        description="Jira Cloud admin helpers. Read-only unless a command says otherwise.")
    sub = parser.add_subparsers(dest="command", required=True)
    p_users = sub.add_parser("users", help="list Atlassian user accounts")
    p_users.add_argument("--inactive-only", action="store_true", help="only deactivated accounts")
    return parser


def make_client():
    base, email, token = config.from_env()
    return JiraClient(base, email, token)


def cmd_users(client, args, out):
    for user in users.human_users(client):
        if args.inactive_only and user.get("active"):
            continue
        out.write("{}\t{}\t{}\t{}\n".format(
            user["accountId"], "active" if user.get("active") else "inactive",
            user.get("displayName", ""), user.get("emailAddress", "")))
    return 0


def main(argv=None, client=None, out=None):
    out = out if out is not None else sys.stdout
    args = build_parser().parse_args(argv)
    try:
        client = client or make_client()
        if args.command == "users":
            return cmd_users(client, args, out)
    except (config.ConfigError, JiraError) as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 2
    return 0
