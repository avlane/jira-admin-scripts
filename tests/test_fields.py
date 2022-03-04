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


class UsageTests(unittest.TestCase):
    def test_counts_and_unqueryable_fields(self):
        from tests.helpers import FakeResponse

        def search(call):
            jql = call["params"]["jql"]
            if "10020" in jql:
                return FakeResponse(400, {"errorMessages": ["The field 'cf[10020]' cannot be searched."]})
            return {"total": {"cf[10010] is not EMPTY": 120, "cf[10032] is not EMPTY": 0}.get(jql, 3)}

        session = FakeSession().add("GET", r"/rest/api/3/field$", load("field_list.json"))
        session.add("GET", r"/rest/api/3/search$", search)
        client = make_client(session)
        rows = fields.usage(client, fields.custom_fields(client))
        by_id = {r["id"]: r["issues"] for r in rows}
        self.assertEqual(by_id["customfield_10010"], 120)
        self.assertEqual(by_id["customfield_10032"], 0)
        self.assertIsNone(by_id["customfield_10020"])
        self.assertEqual([r["id"] for r in fields.unused(rows)], ["customfield_10032"])

    def test_other_errors_propagate(self):
        from tests.helpers import FakeResponse
        from jiraadmin.client import JiraError
        session = FakeSession().add("GET", r"/rest/api/3/search$", FakeResponse(403, {"errorMessages": ["no"]}))
        client = make_client(session)
        with self.assertRaises(JiraError):
            fields.usage(client, [fields.custom_fields(make_client())[0]])


if __name__ == "__main__":
    unittest.main()
