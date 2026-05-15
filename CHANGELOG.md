# Changelog

## 1.0.0

- Python 3.10 or newer; profiles in a TOML file (`--profile`, `--config`).
- `doctor` checks credentials, the Administer Jira permission and that the site is Jira Cloud.
- Bulk group CSV accepts a `groupId` column and rejects contradicting rows.
- Clear messages for 401 and 403; the client refuses very long `Retry-After` waits.

## 0.9

- Enhanced `search/jql` with `nextPageToken`, an approximate issue count, `count` command.
- Stale and empty project report, `archive-projects`, workflow and empty-group reports.
- Request pacing and `X-RateLimit-*` header handling; `--output-dir` and `--progress`.

## 0.8

- Webhook inventory, screen and workflow scheme reports, dashboard and filter ownership transfer.
- Deactivated role holders, duplicate permission schemes, Markdown output.

## 0.5

- Custom field audit with field search usage data and `trash-fields`.
- Filter and dashboard audits, project role audit, permission scheme report.

## 0.1

- Users, inactive users, licence seats, group membership from CSV.
