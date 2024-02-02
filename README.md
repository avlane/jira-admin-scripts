# jira-admin-scripts

Small Python scripts for routine Jira Cloud administration, built on the REST API
with an email address and an API token. Nothing here changes anything unless you
explicitly ask it to.

Status: just started. The plan is user and licence audits first, then group
membership, project roles, permission schemes and custom fields.

## Install

    python -m pip install .

This installs a `jiraadmin` command; `python -m jiraadmin` works from a checkout too.

## Usage

    python -m jiraadmin users --inactive-only
    python -m jiraadmin inactive --days 120 --format csv
    python -m jiraadmin licenses --warn-at 85
    python -m jiraadmin roles --findings-only
    python -m jiraadmin fields --duplicates
    python -m jiraadmin fields --unused
    python -m jiraadmin filters --findings-only
    python -m jiraadmin dashboards --findings-only

Every command takes `--format table|csv|json|markdown`, and `-v` shows requests and rate-limit waits on stderr.

## Bulk group membership

`bulk-groups` reads a CSV and adds the listed accounts to groups:

    action,group,accountId
    add,jira-software-users,5b10ac8d82e05b22cc7d4ef5

`action` is `add` or `remove`. It is a dry run unless `--apply` is passed.
Accounts that are already in (or already out of) the group are skipped.

## Configuration

    export JIRA_URL=https://example.atlassian.net
    export JIRA_EMAIL=you@example.com
    export JIRA_API_TOKEN=...      # https://id.atlassian.com/manage-profile/security/api-tokens

Optional: `JIRA_MAX_RETRIES` (default 5) is how many times a rate-limited request is retried,
and `JIRA_TIMEOUT` (default 30) is the per-request timeout in seconds.
