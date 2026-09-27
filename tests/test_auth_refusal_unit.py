"""#38: a refused authentication must name the authentication MODE.

Measured on TheHive 5.7.5: the add-on's `password` mode sends HTTP Basic, and
TheHive decodes Basic as `user:password[:otp]` by splitting on EVERY ':'
(scalligraph `BasicAuthSrv`). A password containing ':' is therefore cut at its
first ':' and can never authenticate that way, while the same credentials pass
through `/api/v1/login`. The add-on used to report a bare
`THEHIVE_CONNECTION_ERROR - AuthenticationError`, which accuses the password
the user knows to be right.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _isolation import mocks_temporaires  # noqa: E402

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(APP_ROOT, "TA-thehive-cortex", "package", "bin")
for path in (BIN, os.path.join(BIN, "ta_thehive_cortex"),
             os.path.join(BIN, "ta_thehive_cortex", "libs")):
    sys.path.insert(0, path)

MOCKS = [
    "splunklib", "splunklib.client", "solnlib", "solnlib.log",
    "solnlib.modular_input", "solnlib.utils", "ta_thehive_cortex_declare",
    "certifi", "common", "ta_logging", "requests", "requests.adapters",
    "requests.auth", "urllib3",
]

with mocks_temporaires(MOCKS):
    import thehive
    from thehive4py.errors import TheHiveError

#: A dummy credential, never a real one. It carries ':' on purpose: it is the
#: shape that TheHive's Basic parser truncates.
DUMMY_PASSWORD = "dummy:value-for-tests"


def _refusal(status):
    response = MagicMock()
    response.status_code = status
    return TheHiveError(message="AuthenticationError - Authentication failure.", response=response)


class TestAuthenticationRefusalNamesTheMode(unittest.TestCase):

    def _connect(self, error, **credentials):
        """Build a TheHive4Splunk whose first request raises `error`.

        Returns (exit code, [(log id, message), ...]).
        """
        logger = MagicMock()

        def fake_api_init(api_self, *args, **kwargs):
            api_self.user = MagicMock()
            api_self.user.get_current.side_effect = error

        with patch.object(thehive.TheHiveApi, "__init__", fake_api_init), \
                patch.object(thehive, "Utils", MagicMock()):
            with self.assertRaises(SystemExit) as raised:
                thehive.TheHive4Splunk(
                    url="https://thehive.invalid", username="someone",
                    verify=True, version="TheHive5", logger_file=logger,
                    **credentials,
                )
        logged = [
            (call.kwargs.get("id"), call.kwargs.get("message", ""))
            for call in logger.error.call_args_list + logger.warn.call_args_list
        ]
        return raised.exception.code, logged

    def test_password_mode_refusal_names_the_mode_and_the_colon_trap(self):
        code, logged = self._connect(_refusal(401), password=DUMMY_PASSWORD)
        ids = [log_id for log_id, _ in logged]
        self.assertIn("TH111", ids, "a 401 in password mode must not fall into TH110")
        self.assertEqual(111, code)
        message = dict(logged)["TH111"]
        self.assertIn("password", message)
        self.assertIn("HTTP Basic", message)
        self.assertIn("':'", message, "the colon truncation is the measured cause")
        self.assertIn("api_key", message, "the working alternative must be named")

    def test_api_key_mode_refusal_names_the_mode(self):
        code, logged = self._connect(_refusal(401), apiKey="dummy-key-for-tests")
        message = dict(logged).get("TH111", "")
        self.assertEqual(111, code)
        self.assertIn("api_key", message)
        self.assertNotIn("HTTP Basic", message, "the Basic hints do not apply to a key")

    def test_refusal_is_recognised_without_a_response_object(self):
        # thehive4py does not always attach the response; the message is what
        # remains, and it is the one TheHive 5 sends.
        error = TheHiveError(message="AuthenticationError - Authentication failure.")
        code, logged = self._connect(error, password=DUMMY_PASSWORD)
        self.assertEqual(111, code)

    def test_other_failures_keep_the_connection_error(self):
        code, logged = self._connect(_refusal(500), password=DUMMY_PASSWORD)
        self.assertEqual(110, code)
        self.assertNotIn("TH111", [log_id for log_id, _ in logged])

    def test_no_message_carries_the_credential(self):
        for credentials in ({"password": DUMMY_PASSWORD}, {"apiKey": "dummy-key-for-tests"}):
            _, logged = self._connect(_refusal(401), **credentials)
            secret = next(iter(credentials.values()))
            for log_id, message in logged:
                self.assertNotIn(secret, message, log_id)
                self.assertNotIn(secret.split(":")[0], message, log_id)


class TestUnreadableAnswerLogsNoCredential(unittest.TestCase):
    """TH46 used to log `session.headers`, i.e. `Authorization` and its value."""

    def test_th46_logs_header_names_not_values(self):
        logger = MagicMock()
        key = "dummy-key-for-tests"

        def fake_api_init(api_self, *args, **kwargs):
            api_self.user = MagicMock()
            api_self.user.get_current.return_value = {}  # no "_id": TH45/TH46 path
            api_self.session = MagicMock()
            api_self.session.headers = {"Authorization": f"Bearer {key}", "User-Agent": "x"}

        with patch.object(thehive.TheHiveApi, "__init__", fake_api_init), \
                patch.object(thehive, "Utils", MagicMock()):
            thehive.TheHive4Splunk(
                url="https://thehive.invalid", apiKey=key, verify=True,
                version="TheHive5", logger_file=logger,
            )
        debug = {c.kwargs.get("id"): c.kwargs.get("message", "") for c in logger.debug.call_args_list}
        self.assertIn("TH46", debug)
        self.assertIn("Authorization", debug["TH46"], "the header NAME is useful and harmless")
        for log_id, message in debug.items():
            self.assertNotIn(key, message, log_id)


if __name__ == "__main__":
    unittest.main()
