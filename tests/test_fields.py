import unittest

from jiraadmin import fields
from jiraadmin.client import JiraClient
from tests.helpers import FakeSession, load


def make_client(session=None):
    session = session or FakeSession().add("GET", r"/rest/api/3/field$", load("field_list.json"))
    return JiraClient("https://example.atlassian.net", session=session)


class FieldListTests(unittest.TestCase):
    def test_only_custom_fields(self):
        got = fields.custom_fields(make_client())
        self.assertEqual(len(got), 7)
        self.assertTrue(all(f["custom"] for f in got))

    def test_field_type_uses_the_plugin_key_suffix(self):
        by_id = {f["id"]: f for f in fields.custom_fields(make_client())}
        self.assertEqual(fields.field_type(by_id["customfield_10030"]), "select")
        self.assertEqual(fields.field_type(by_id["customfield_10020"]), "gh-sprint")

    def test_duplicates_ignore_case_but_not_type(self):
        rows = fields.duplicate_rows(fields.custom_fields(make_client()))
        self.assertEqual([(r["name"], r["ids"]) for r in rows], [
            ("Story Points", ["customfield_10010", "customfield_10011"]),
            ("Customer Impact", ["customfield_10030", "customfield_10031"])])

    def test_same_name_different_type_is_not_a_duplicate(self):
        a = {"id": "customfield_1", "name": "Owner", "schema": {"custom": "x:userpicker"}}
        b = {"id": "customfield_2", "name": "owner", "schema": {"custom": "x:textfield"}}
        self.assertEqual(fields.duplicates([a, b]), [])


if __name__ == "__main__":
    unittest.main()
