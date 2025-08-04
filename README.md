# jira-admin-scripts

Python scripts for routine Jira Cloud administration, built on the REST API with an
email address and an API token. Everything that changes data is a dry run unless
`--apply` is passed, and every HTTP call goes through an injectable session so the
code can be tested against recorded JSON.

## Install

    python -m pip install .

This installs a `jiraadmin` command; `python -m jiraadmin` works from a checkout too.
The only runtime dependency is `requests`, imported lazily.

## Configuration

    export JIRA_URL=https://example.atlassian.net
    export JIRA_EMAIL=you@example.com
    export JIRA_API_TOKEN=...      # https://id.atlassian.com/manage-profile/security/api-tokens

Optional: `JIRA_MAX_RETRIES` (default 5) is how many times a rate-limited or briefly
unavailable request is retried, and `JIRA_TIMEOUT` (default 30) is the per-request
timeout in seconds. `JIRA_REQUESTS_PER_SECOND` spaces requests out (for example `2`). The account
needs Administer Jira for most commands.

## Commands

| command | what it does |
| --- | --- |
| `users` | Atlassian user accounts (apps and customers are skipped) |
| `inactive` | active accounts with no recent issue activity; `--exclude-file` skips listed accounts |
| `licenses` | seat usage per application, with a warning threshold |
| `group-members` | members of a group, by name or `--group-id` |
| `bulk-groups FILE.csv` | add or remove group members from `action,group,accountId` rows |
| `roles` | who holds each project role; `--check-users` flags deactivated people |
| `permissions` | permission schemes and their projects; `--grants`, `--duplicates` |
| `fields` | custom fields; `--duplicates`, `--unused` |
| `trash-fields` | move abandoned custom fields to the trash |
| `filters`, `dashboards` | orphaned and idle filters and dashboards |
| `transfer-filters`, `transfer-dashboards` | give orphaned ones to another owner |
| `webhooks` | admin-registered webhooks, with risky-setting flags |
| `screens` | screens no scheme uses; `--schemes` for issue type screen schemes |
| `workflow-schemes` | workflow schemes and the projects that use them |
| `workflows` | workflows no scheme uses |
| `count` | how many issues match a JQL query |

Every command takes `--format table|csv|json|markdown`, and `-v` shows requests and
rate-limit waits on stderr. Notices and summaries go to stderr, so JSON and CSV on
stdout can be piped as they are.

## Dry runs

Commands that change anything (`bulk-groups`, `trash-fields`, `transfer-*`) print what
they would do and stop. Add `--apply` to make the change. Bulk group changes check that
each account to add exists and is active before sending anything.

## Rate limits and retries

Atlassian is moving Jira Cloud to points-based rate limits. Responses may carry
`X-RateLimit-NearLimit`, `X-RateLimit-Remaining` and `X-RateLimit-Reset` headers; when
`NearLimit` is true the client pauses until the reset time (at most 10 seconds) before it
sends more. A 429 is logged with its `RateLimit-Reason` header when there is one.
Set `JIRA_REQUESTS_PER_SECOND` to stay well under the limit on big audits.

HTTP 429 responses are retried after the `Retry-After` delay (seconds or an HTTP date).
502, 503 and 504 are retried with a short backoff for GET, PUT and DELETE, never for POST.

## Tests

    python -m unittest discover

The tests replay JSON recorded from a fictional `example.atlassian.net`; nothing
touches the network.
