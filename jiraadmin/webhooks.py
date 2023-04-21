"""Webhook inventory (admin-registered webhooks)."""
from datetime import datetime, timezone
from urllib.parse import urlsplit


def list_webhooks(client):
    """Webhooks created under System > Webhooks, via the webhooks REST resource."""
    return client.get("/rest/webhooks/1.0/webhook") or []


def _host(url):
    return urlsplit(url).hostname or ""


def _updated(ms):
    if not ms:
        return ""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def findings(hook, internal_domains=()):
    """Things worth checking about one webhook.

    disabled       registered but switched off
    plain-http     payloads (which can include issue text) travel unencrypted
    secret-in-url  a query string, usually a token, is stored in the webhook URL
    no-filter      fires for every project because it has no JQL filter
    external       the receiving host is outside the domains you listed as internal
    """
    url = urlsplit(hook.get("url", ""))
    found = []
    if not hook.get("enabled", False):
        found.append("disabled")
    if url.scheme == "http":
        found.append("plain-http")
    if url.query or url.password:
        found.append("secret-in-url")
    if not (hook.get("filters") or {}).values():
        found.append("no-filter")
    host = url.hostname or ""
    if internal_domains and not any(host == dom or host.endswith("." + dom) for dom in internal_domains):
        found.append("external")
    return found


def inventory(client, internal_domains=()):
    rows = []
    for hook in list_webhooks(client):
        rows.append({
            "name": hook["name"], "host": _host(hook.get("url", "")), "enabled": hook.get("enabled", False),
            "events": len(hook.get("events", [])), "filter": "; ".join((hook.get("filters") or {}).values()),
            "lastUpdatedBy": hook.get("lastUpdatedDisplayName", ""), "lastUpdated": _updated(hook.get("lastUpdated")),
            "id": hook.get("self", "").rsplit("/", 1)[-1],
            "findings": findings(hook, internal_domains)})
    return rows
