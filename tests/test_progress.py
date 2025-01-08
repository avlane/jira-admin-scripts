import io
import unittest

from jiraadmin.progress import Progress


class ProgressTests(unittest.TestCase):
    def test_reports_every_n_items_and_at_the_end(self):
        stream = io.StringIO()
        progress = Progress("users", stream=stream, every=2)
        for _ in range(5):
            progress.tick()
        progress.finish()
        self.assertEqual(stream.getvalue().splitlines(), ["users: 2 checked", "users: 4 checked", "users: 5 checked"])

    def test_no_duplicate_final_line(self):
        stream = io.StringIO()
        progress = Progress("x", stream=stream, every=2)
        progress.tick()
        progress.tick()
        progress.finish()
        self.assertEqual(stream.getvalue().splitlines(), ["x: 2 checked"])

    def test_disabled_is_silent(self):
        stream = io.StringIO()
        progress = Progress("x", stream=stream, every=1, enabled=False)
        progress.tick()
        progress.finish()
        self.assertEqual(stream.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
