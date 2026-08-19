"""No HTTP call may hold a Splunk worker until the OS gives up.

`requests` has no default timeout. A server that ACCEPTS the connection and
then says nothing is the nasty case: the socket is established, so nothing
looks broken, and the caller waits for the kernel's read timeout -- minutes.
Inside Splunk that is a search command or a modular input pinning its worker
while the search merely looks slow.

The test uses a real listening socket that never answers, because that is the
only way to tell a bounded call from an unbounded one: mocking `requests` would
prove that we PASS a timeout, not that one APPLIES.
"""

import importlib.util
import os
import socket
import sys
import threading
import unittest

#: The suite must run without Splunk's bundled libraries. Skipping is the only
#: honest option -- and it has to SAY it skipped, not die like the old harness.
REQUESTS_DISPONIBLE = importlib.util.find_spec("requests") is not None

mocks = [
    'splunklib', 'splunklib.client', 'solnlib', 'solnlib.log',
    'solnlib.modular_input', 'solnlib.utils', 'ta_thehive_cortex_declare',
    'splunk', 'splunk.Intersplunk', 'globals', 'common', 'ta_logging', 'tomark',
]

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _isolation import mocks_temporaires  # noqa: E402

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(APP_ROOT, 'TA-thehive-cortex', 'package', 'bin')
for p in (BIN, os.path.join(BIN, 'ta_thehive_cortex', 'libs')):
    if p not in sys.path:
        sys.path.insert(0, p)

# `requests` is NOT mocked here: the whole point is a real socket call.
# ⚠️ The guard has to wrap the IMPORT, not just the test methods: without
# `requests` the module fails to load and unittest reports an error, which is
# exactly the "dies instead of skipping" behaviour this suite was cured of.
if REQUESTS_DISPONIBLE:
    with mocks_temporaires(mocks):
        from thehive4py.session import TheHiveSession
        from cortex4py.api import Api


class ServeurMuet:
    """Accepts the connection, then never writes a byte."""

    def __init__(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(8)
        self.port = self._sock.getsockname()[1]
        self._stop = threading.Event()
        self._retenues = []
        self._fil = threading.Thread(target=self._boucle, daemon=True)
        self._fil.start()

    def _boucle(self):
        self._sock.settimeout(0.2)
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except (socket.timeout, OSError):
                continue
            # Kept open on purpose: closing would end the wait and hide the bug.
            self._retenues.append(conn)

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}"

    def fermer(self):
        self._stop.set()
        self._fil.join(timeout=2)
        for c in self._retenues:
            try:
                c.close()
            except OSError:
                pass
        self._sock.close()


@unittest.skipUnless(REQUESTS_DISPONIBLE, "requests is not installed here")
class TestDelaiHttp(unittest.TestCase):

    #: Short enough to keep the suite fast, long enough not to fire by accident.
    DELAI = 2
    #: The wait must stay in the same order of magnitude as the timeout.
    #: Retries multiply it, so the margin is generous on purpose.
    PLAFOND = 15

    def setUp(self):
        self.serveur = ServeurMuet()
        self.addCleanup(self.serveur.fermer)

    def _rend_la_main_avant_le_plafond(self, appel):
        """Run the call in a thread and judge on the JOIN, not on a stopwatch.

        ⚠️ Measuring elapsed time after the call returns would make this test
        HANG instead of failing when the timeout is missing: the call would sit
        there for the OS TCP timeout, minutes long, and the assertion would only
        run afterwards. Joining with a deadline fails fast and never hangs --
        which is what makes it usable in CI.
        """
        issue = {}

        def executer():
            try:
                appel()
                issue["resultat"] = "returned without raising"
            except Exception as err:  # noqa: BLE001
                issue["resultat"] = type(err).__name__

        fil = threading.Thread(target=executer, daemon=True)
        fil.start()
        fil.join(timeout=self.PLAFOND)
        self.assertFalse(
            fil.is_alive(),
            f"the call was still waiting after {self.PLAFOND}s: no timeout applied",
        )
        self.assertIn("resultat", issue)

    def test_thehive_session_rend_la_main(self):
        # ⚠️ `max_retries=None` ON PURPOSE. The library ships DEFAULT_RETRY with
        # total=5 and backoff_factor=1, so the timeout bounds each ATTEMPT and
        # the retries multiply the wait: 6 attempts plus 0+2+4+8+16s of backoff.
        # A 60s setting therefore allows several MINUTES of total waiting. That
        # is bounded -- which is the point of this ticket -- but it is not what
        # the setting says, and it deserves to be known.
        # Here we isolate the timeout itself.
        session = TheHiveSession(url=self.serveur.url, apikey="0" * 12,
                                 timeout=self.DELAI, max_retries=None)
        # ⚠️ NOT `session.get("/api/v1/status")`: a relative URL makes
        # requests raise MissingSchema instantly, and the test would pass in
        # 0.2s WITHOUT EVER OPENING A SOCKET -- green for the wrong reason.
        # make_request() is what the add-on actually calls, and it builds the
        # absolute URL.
        self._rend_la_main_avant_le_plafond(
            lambda: session.make_request("GET", "/api/v1/status")
        )

    def test_cortex_api_rend_la_main(self):
        api = Api(self.serveur.url, "0" * 12, timeout=self.DELAI)
        self._rend_la_main_avant_le_plafond(lambda: api.do_get("status"))


if __name__ == '__main__':
    unittest.main()
