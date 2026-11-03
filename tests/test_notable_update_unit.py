"""Marking a notable as handled: best effort, never raises, opt-in."""

import os
import sys
import unittest

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(APP_ROOT, 'TA-thehive-cortex', 'package', 'bin')
for p in (BIN, os.path.join(BIN, 'ta_thehive_cortex')):
    if p not in sys.path:
        sys.path.insert(0, p)

from notable_update import mark_notable_handled  # noqa: E402


class Logger:
    def __init__(self):
        self.rows = []

    def info(self, id="?", message=""):
        self.rows.append(("info", id))

    def warning(self, id="?", message=""):
        self.rows.append(("warning", id))


class Response:
    def __init__(self, status):
        self.status = status


class MarkNotable(unittest.TestCase):
    def test_success_sends_the_event_id_and_status(self):
        seen = {}

        def request(path, key, postargs):
            seen.update(path=path, key=key, post=postargs)
            return Response(200), b"ok"

        log = Logger()
        self.assertTrue(mark_notable_handled("K", "uid@@notable@@t1", 5, log, request))
        self.assertEqual(seen["path"], "/services/notable_update")
        self.assertEqual(seen["post"]["ruleUIDs"], "uid@@notable@@t1")
        self.assertEqual(seen["post"]["status"], "5")
        self.assertEqual(log.rows, [("info", "127")])

    def test_http_error_is_a_warning_not_an_exception(self):
        log = Logger()
        self.assertFalse(mark_notable_handled(
            "K", "x", 5, log, lambda *a: (Response(403), b"no capability")))
        self.assertEqual(log.rows, [("warning", "128")])

    def test_exception_is_a_warning_not_an_exception(self):
        def boom(*a):
            raise RuntimeError("down")

        log = Logger()
        self.assertFalse(mark_notable_handled("K", "x", 5, log, boom))
        self.assertEqual(log.rows, [("warning", "129")])


if __name__ == "__main__":
    unittest.main()
