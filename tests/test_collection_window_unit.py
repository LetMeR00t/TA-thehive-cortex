"""A live input must not lose a window, and must not collect one twice.

⚠️ From production (3.9.0 on a heavy forwarder, TheHive 5.6.7): each run asked
for exactly the last interval. Failed runs (proxy, authentication, KeyError),
runs blocked by a hang, runs skipped while splunkd restarted, and even healthy
runs that asked 0.4 s after the window ended -- before TheHive had made an entry
stamped 11:08:59 visible -- each lost their window for good.
"""

import os
import sys
import unittest

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(APP_ROOT, "TA-thehive-cortex", "package", "bin", "ta_thehive_cortex"))

import collection_window as cw  # noqa: E402

NOW = 1793180000.0  # epoch seconds


class Log:
    def __init__(self):
        self.lines = []

    def info(self, id="?", message=""):
        self.lines.append(("INFO", id, message))

    def warn(self, id="?", message=""):
        self.lines.append(("WARNING", id, message))

    def error(self, id="?", message=""):
        self.lines.append(("ERROR", id, message))

    def ids(self):
        return [i for _, i, _ in self.lines]


class DictStore:
    """Stands in for solnlib's checkpointer: get/update by key."""

    def __init__(self, fail_update=False):
        self.data, self.fail_update = {}, fail_update

    def get(self, key):
        return self.data.get(key)

    def update(self, key, state):
        if self.fail_update:
            raise IOError("KV store down")
        self.data[key] = state


def windows(store, item=None, state=("disabled", None, None)):
    w = cw.CollectionWindows({"session_key": "k", "checkpoint_dir": "/tmp"}, "thehive_audit://org_a", item or {"interval": "60"}, Log())
    w._store = store
    w._cluster_state = lambda: state
    return w


class TestPlan(unittest.TestCase):

    def test_first_run_is_one_interval_ending_lag_ago(self):
        self.assertEqual((int((NOW - 120) * 1000), int((NOW - 60) * 1000)), cw.plan(None, NOW, 60))

    def test_continues_from_the_watermark(self):
        start = int((NOW - 300) * 1000)
        self.assertEqual((start, int((NOW - 60) * 1000)), cw.plan(start, NOW, 60))

    def test_catch_up_is_capped(self):
        start = int((NOW - 86400) * 1000)
        self.assertEqual((start, start + 6 * 3600 * 1000), cw.plan(start, NOW, 60))

    def test_nothing_due_yet(self):
        self.assertIsNone(cw.plan(int((NOW - 60) * 1000), NOW, 60))

    def test_windows_join_exactly_across_failures(self):
        """Runs every 60 s; every third one fails before writing: the windows collected still tile time."""
        store, collected, t = DictStore(), [], NOW
        for run in range(30):
            w = windows(store)
            span = w.next("audit", t)
            if span and run % 3 != 1:
                collected.append(span)
                w.done("audit", span, 0)
            t += 60 + (run % 5)          # irregular start times, as with a busy scheduler
        for (a, b), (c, d) in zip(collected, collected[1:]):
            self.assertEqual(b, c)        # no gap, no overlap: TheHive's _between is [from, to)


class TestWatermark(unittest.TestCase):

    def test_failed_run_keeps_the_watermark(self):
        store = DictStore()
        w = windows(store)
        first = w.next("audit", NOW)
        w.done("audit", first, 3)
        failed = windows(store).next("audit", NOW + 60)       # this run fails: no done()
        again = windows(store).next("audit", NOW + 120)
        self.assertEqual(first[1], failed[0])
        self.assertEqual(failed[0], again[0])                 # the failed window is collected again
        self.assertEqual(int((NOW + 120 - 60) * 1000), again[1])

    def test_unsaved_watermark_is_an_error_and_the_window_repeats(self):
        w = windows(DictStore(fail_update=True))
        span = w.next("audit", NOW)
        w.done("audit", span, 5)
        self.assertIn("CKPT", w._logger.ids())
        self.assertNotIn("DONE", w._logger.ids())

    def test_pulls_and_inputs_are_independent(self):
        store = DictStore()
        a = windows(store)
        a.done("alerts:_createdAt", a.next("alerts:_createdAt", NOW), 1)
        self.assertIsNone(windows(store).next("alerts:_createdAt", NOW))
        self.assertIsNotNone(windows(store).next("alerts:_updatedAt", NOW))
        other = cw.CollectionWindows({"session_key": "k"}, "thehive_audit://org_b", {"interval": "60"}, Log())
        other._store = store
        self.assertIsNotNone(other.next("alerts:_createdAt", NOW))

    def test_run_lines_name_the_input(self):
        w = windows(DictStore())
        w.done("audit", w.next("audit", NOW), 7)
        messages = [m for _, _, m in w._logger.lines]
        self.assertTrue(messages[0].startswith("input=thehive_audit://org_a pull=audit window="))
        self.assertIn("events=7", messages[1])

    def test_settings(self):
        self.assertEqual(60, cw.setting({}, "lag_seconds", 60))
        self.assertEqual(60, cw.setting({"lag_seconds": ""}, "lag_seconds", 60))
        self.assertEqual(60, cw.setting({"lag_seconds": "x"}, "lag_seconds", 60))
        self.assertEqual(0, cw.setting({"lag_seconds": "0"}, "lag_seconds", 60))
        self.assertEqual(120, cw.setting({"lag_seconds": " 120 "}, "lag_seconds", 60))


class TestSearchHeadCluster(unittest.TestCase):

    def test_not_clustered_collects(self):
        self.assertTrue(cw.should_collect("disabled", None, None)[0])
        self.assertTrue(cw.should_collect(None, None, None)[0])

    def test_only_the_captain_collects(self):
        self.assertTrue(cw.should_collect("member", "sh1", "sh1")[0])
        self.assertFalse(cw.should_collect("member", "sh1", "sh2")[0])

    def test_no_known_captain_waits(self):
        self.assertFalse(cw.should_collect("member", None, "sh2")[0])

    def test_a_member_that_is_not_captain_logs_and_does_not_collect(self):
        w = windows(DictStore(), state=("member", "sh1", "sh2"))
        self.assertFalse(w.collect_here())
        self.assertEqual(["SKIP"], w._logger.ids())


class TestWatermarkStore(unittest.TestCase):
    """⚠️ From a live test (Splunk 9.3.14, [kvstore] disabled = true): solnlib's KV
    checkpointer opened without error and failed on its first read with HTTP 503,
    so the old "try the KV store, fall back on error" never fell back -- every
    run failed and nothing was collected."""

    def windows_with_kv(self, kv_state, fail_open=False):
        w = windows(None)
        w._kv_state = lambda: kv_state
        w.opened = []

        def make(store):
            if fail_open:
                raise IOError("cannot open")
            w.opened.append(store)
            return DictStore()
        w._make_store = make
        return w

    def test_choice(self):
        self.assertEqual("file", cw.store_choice(True, None)[0])
        self.assertEqual("file", cw.store_choice("1", None)[0])
        self.assertEqual("file", cw.store_choice("true", "ready")[0])
        self.assertEqual("kv", cw.store_choice(False, "ready")[0])
        self.assertEqual("kv", cw.store_choice("0", "ready")[0])
        self.assertEqual("wait", cw.store_choice(False, "starting")[0])
        self.assertEqual("wait", cw.store_choice(False, None)[0])

    def test_a_disabled_kv_store_never_reaches_the_kv_checkpointer(self):
        w = self.windows_with_kv((True, None))
        self.assertTrue(w.collect_here())
        self.assertEqual(["file"], w.opened)
        self.assertEqual(["KV"], w._logger.ids())
        self.assertIsNotNone(w.next("audit", NOW))

    def test_a_ready_kv_store_is_used_silently(self):
        w = self.windows_with_kv((False, "ready"))
        self.assertTrue(w.collect_here())
        self.assertEqual(["kv"], w.opened)
        self.assertEqual([], w._logger.ids())

    def test_a_starting_kv_store_skips_the_run_without_a_second_watermark(self):
        w = self.windows_with_kv((False, "starting"))
        self.assertFalse(w.collect_here())
        self.assertEqual([], w.opened)                       # no file watermark started
        self.assertEqual(["KVWAIT"], w._logger.ids())
        self.assertIn("status=starting", w._logger.lines[0][2])

    def test_a_store_that_cannot_be_opened_skips_the_run(self):
        w = self.windows_with_kv((False, "ready"), fail_open=True)
        self.assertFalse(w.collect_here())
        self.assertEqual(["KVOPEN"], w._logger.ids())

    def test_a_non_captain_does_not_look_at_the_kv_store(self):
        w = self.windows_with_kv((False, "starting"))
        w._cluster_state = lambda: ("member", "sh1", "sh2")
        self.assertFalse(w.collect_here())
        self.assertEqual(["SKIP"], w._logger.ids())


if __name__ == "__main__":
    unittest.main()
