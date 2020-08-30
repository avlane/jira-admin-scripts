# jira-admin-scripts

Small Python scripts for routine Jira Cloud administration, built on the REST API
with an email address and an API token. Nothing here changes anything unless you
explicitly ask it to.

Status: just started. The plan is user and licence audits first, then group
membership, project roles, permission schemes and custom fields.

## Usage

    python -m jiraadmin users --inactive-only
    python -m jiraadmin inactive --days 120 --format csv
    python -m jiraadmin licenses --warn-at 85

Every command takes `--format table|csv|json`.

## Bulk group membership

`bulk-groups` reads a CSV and adds the listed accounts to groups:

    action,group,accountId
    add,jira-software-users,5b10ac8d82e05b22cc7d4ef5

It is a dry run unless `--apply` is passed. Accounts that are already in the
group are skipped.

## Configuration

    export JIRA_URL=https://example.atlassian.net
    export JIRA_EMAIL=you@example.com
    export JIRA_API_TOKEN=...      # https://id.atlassian.com/manage-profile/security/api-tokens
