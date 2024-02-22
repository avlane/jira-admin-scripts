import csv
import io
import json
import unittest

from jiraadmin import report

ROWS = [{"name": "Alice", "n": 3, "ok": True, "tags": ["a", "b"]}, {"name": "Bob", "n": None, "ok": False}]
COLS = ("name", "n", "ok", "tags")


class ReportTests(unittest.TestCase):
    def test_table_aligns_columns(self):
        lines = report.render(ROWS, COLS).splitlines()
        self.assertEqual(lines[0], "name   n  ok   tags")
        self.assertEqual(lines[1], "-----  -  ---  ----")
        self.assertEqual(lines[2], "Alice  3  yes  a, b")
        self.assertEqual(lines[3], "Bob       no")

    def test_csv_round_trips(self):
        parsed = list(csv.reader(io.StringIO(report.render(ROWS, COLS, "csv"))))
        self.assertEqual(parsed[0], list(COLS))
        self.assertEqual(parsed[2], ["Bob", "", "no", ""])

    def test_json_keeps_full_rows(self):
        self.assertEqual(json.loads(report.render(ROWS, COLS, "json")), ROWS)

    def test_line_breaks_do_not_split_table_rows(self):
        rows = [{"name": "Default Screen", "description": "Allows to update\nall   system fields.\r\n"}]
        lines = report.render(rows, ("name", "description")).splitlines()
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[2], "Default Screen  Allows to update all system fields.")

    def test_csv_keeps_line_breaks(self):
        rows = [{"description": "one\ntwo"}]
        parsed = list(csv.reader(io.StringIO(report.render(rows, ("description",), "csv"))))
        self.assertEqual(parsed[1], ["one\ntwo"])

    def test_markdown(self):
        lines = report.render(ROWS, COLS, "markdown").splitlines()
        self.assertEqual(lines[0], "| name | n | ok | tags |")
        self.assertEqual(lines[1], "| --- | --- | --- | --- |")
        self.assertEqual(lines[2], "| Alice | 3 | yes | a, b |")
        self.assertEqual(lines[3], "| Bob |  | no |  |")

    def test_markdown_escapes_pipes(self):
        self.assertIn("a \\| b", report.render([{"x": "a | b"}], ("x",), "markdown"))

    def test_empty_table(self):
        self.assertEqual(report.render([], COLS), "(no rows)\n")

    def test_unknown_format(self):
        with self.assertRaises(ValueError):
            report.render(ROWS, COLS, "xml")


if __name__ == "__main__":
    unittest.main()
