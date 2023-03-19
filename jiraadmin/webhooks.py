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


def inventory(client):
    rows = []
    for hook in list_webhooks(client):
        rows.append({
            "name": hook["name"], "host": _host(hook.get("url", "")), "enabled": hook.get("enabled", False),
            "events": len(hook.get("events", [])), "filter": "; ".join((hook.get("filters") or {}).values()),
            "lastUpdatedBy": hook.get("lastUpdatedDisplayName", ""), "lastUpdated": _updated(hook.get("lastUpdated")),
            "id": hook.get("self", "").rsplit("/", 1)[-1]})
    return rows
