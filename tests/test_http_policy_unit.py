"""http_policy: a short connect timeout, and a read timeout is never retried.

The retry check uses a real listening socket that never answers and COUNTS the
connections it accepts: one connection = the request was sent once. Mocking
`requests` would prove that we pass a Retry object, not what it does.

⚠️ Every check runs in a fresh interpreter. Other tests of this suite replace
`urllib3` and `requests` with mocks while they import the add-on, and a module
imported meanwhile (``http_policy``, ``thehive4py.session``) keeps the mock it
saw: in-process, this test would judge a MagicMock, or disturb the next test.
"""

import importlib.util
import json
import os
import subprocess
import sys
import unittest

REQUESTS_AVAILABLE = importlib.util.find_spec("requests") is not None

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(APP_ROOT, 'TA-thehive-cortex', 'package', 'bin')
PATHS = [os.path.join(BIN, 'ta_thehive_cortex'), os.path.join(BIN, 'ta_thehive_cortex', 'libs')]

PRELUDE = f"""
import json, socket, sys, threading, time
sys.path[:0] = {PATHS!r}
import http_policy
from thehive4py.session import DEFAULT_RETRY, TheHiveSession

def attempts(max_retries, read_s):
    # A server that accepts the connection, then never writes a byte; returns
    # the connections it accepted for one request, and the seconds it took.
    srv = socket.socket(); srv.bind(("127.0.0.1", 0)); srv.listen(8); srv.settimeout(0.2)
    held, stop = [], threading.Event()
    def loop():
        while not stop.is_set():
            try:
                held.append(srv.accept()[0])
            except OSError:
                pass
    threading.Thread(target=loop, daemon=True).start()
    session = TheHiveSession(url="http://127.0.0.1:%d" % srv.getsockname()[1], apikey="0" * 12,
                             timeout=http_policy.timeout(read_s), max_retries=max_retries)
    started = time.monotonic()
    try:
        session.make_request("GET", "/api/v1/status")
    except Exception:
        pass
    elapsed = time.monotonic() - started
    time.sleep(0.3)
    stop.set()
    return len(held), elapsed
"""


def run(code, timeout=60):
    """Run PRELUDE + code in a fresh interpreter; it prints one JSON value."""
    out = subprocess.run([sys.executable, "-c", PRELUDE + code], capture_output=True, text=True, timeout=timeout)
    if out.returncode != 0:
        raise AssertionError(out.stderr[-2000:])
    return json.loads(out.stdout.strip().splitlines()[-1])


@unittest.skipUnless(REQUESTS_AVAILABLE, "requests is not installed here")
class TestHttpPolicy(unittest.TestCase):

    def test_connect_timeout_is_short_and_the_setting_stays_the_read_timeout(self):
        self.assertEqual([[10.0, 60.0], [10.0, 120.0], [5.0, 5.0]], run(
            "print(json.dumps([http_policy.timeout(60), http_policy.timeout('120'), http_policy.timeout(5)]))"))

    def test_read_timeouts_are_not_retried_connection_errors_are(self):
        got = run("r = http_policy.retries(); d = DEFAULT_RETRY; print(json.dumps("
                  "[r.read, r.connect, r.total, sorted(r.status_forcelist) == sorted(d.status_forcelist), r.backoff_factor == d.backoff_factor]))")
        self.assertEqual([0, 5, 5, True, True], got)

    def test_a_silent_server_gets_the_request_once(self):
        sent, elapsed = run("print(json.dumps(attempts(http_policy.retries(), 1)))")
        self.assertEqual(1, sent)
        self.assertLess(elapsed, 4)

    def test_the_library_default_sends_it_again_on_every_read_timeout(self):
        # What 5.0.0 did, with total cut from 5 to 2 to keep the suite fast:
        # 1 + 2 retries = 3 sends (5.0.0: 6 sends, about 6.5 min at 60 s).
        sent, _ = run("print(json.dumps(attempts(DEFAULT_RETRY.new(total=2), 1)))")
        self.assertEqual(3, sent)


if __name__ == "__main__":
    unittest.main()
