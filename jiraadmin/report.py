"""Render lists of dict rows as a text table, CSV or JSON."""
import csv
import io
import json


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(v) for v in value)
    return str(value)


def render(rows: list[dict], columns: tuple[str, ...], fmt: str = "table") -> str:
    if fmt == "json":
        return json.dumps(rows, indent=2) + "\n"
    cells = [[_cell(row.get(col)) for col in columns] for row in rows]
    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(columns)
        writer.writerows(cells)
        return buf.getvalue()
    if fmt != "table":
        raise ValueError("unknown format {!r}".format(fmt))
    if not rows:
        return "(no rows)\n"
    widths = [max([len(col)] + [len(line[i]) for line in cells]) for i, col in enumerate(columns)]
    lines = ["  ".join(col.ljust(w) for col, w in zip(columns, widths)).rstrip(),
             "  ".join("-" * w for w in widths)]
    for line in cells:
        lines.append("  ".join(cell.ljust(w) for cell, w in zip(line, widths)).rstrip())
    return "\n".join(lines) + "\n"
