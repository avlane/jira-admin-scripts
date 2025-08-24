"""The dry-run/apply loop shared by every command that changes something."""
from .client import JiraError


def run_each(items, perform, apply=False, key="id", planned="would change", done="done"):
    """Call perform(item) for each item and report what happened.

    Without apply nothing is called and every item is reported as planned.
    A JiraError marks that one item failed and the loop carries on.
    """
    results = []
    for item in items:
        if not apply:
            results.append({key: item, "status": "planned", "detail": planned})
            continue
        try:
            perform(item)
        except JiraError as exc:
            results.append({key: item, "status": "failed", "detail": str(exc)})
            continue
        results.append({key: item, "status": done, "detail": ""})
    return results
