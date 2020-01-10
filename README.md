# jira-admin-scripts

Small Python scripts for routine Jira Cloud administration, built on the REST API
with an email address and an API token. Nothing here changes anything unless you
explicitly ask it to.

Status: just started. The plan is user and licence audits first, then group
membership, project roles, permission schemes and custom fields.

## Configuration

    export JIRA_URL=https://example.atlassian.net
    export JIRA_EMAIL=you@example.com
    export JIRA_API_TOKEN=...      # https://id.atlassian.com/manage-profile/security/api-tokens
