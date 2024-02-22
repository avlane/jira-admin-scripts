"""Render lists of dict rows as a text table, CSV or JSON."""
import csv
import io
import json


def _cell(value, flat: bool = False) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (list, tuple, set)):
        text = ", ".join(str(v) for v in value)
    else:
        text = str(value)
    # Descriptions often contain line breaks, which would tear a text table apart.
    return " ".join(text.split()) if flat else text


def _markdown(rows, columns):
    """A GitHub-flavoured table, ready to paste into a Jira comment or a pull request."""
    def escape(text):
        return text.replace("|", "\\|")

    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(escape(_cell(row.get(col), flat=True)) for col in columns) + " |")
    return "\n".join(lines) + "\n"


def render(rows: list[dict], columns: tuple[str, ...], fmt: str = "table") -> str:
    if fmt == "json":
        return json.dumps(rows, indent=2) + "\n"
    if fmt == "markdown":
        return _markdown(rows, columns)
    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(columns)
        writer.writerows([_cell(row.get(col)) for col in columns] for row in rows)
        return buf.getvalue()
    if fmt != "table":
        raise ValueError("unknown format {!r}".format(fmt))
    cells = [[_cell(row.get(col), flat=True) for col in columns] for row in rows]
    if not rows:
        return "(no rows)\n"
    widths = [max([len(col)] + [len(line[i]) for line in cells]) for i, col in enumerate(columns)]
    lines = ["  ".join(col.ljust(w) for col, w in zip(columns, widths)).rstrip(),
             "  ".join("-" * w for w in widths)]
    for line in cells:
        lines.append("  ".join(cell.ljust(w) for cell, w in zip(line, widths)).rstrip())
    return "\n".join(lines) + "\n"
