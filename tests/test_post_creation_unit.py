"""Attaching TTPs must never turn a successful creation into a failed action.

⚠️ Measured on TheHive 5.7.5: an account without the `manageProcedure`
permission makes `create_procedures` raise. The exception escaped
`attach_procedures`, killed the alert action, and Splunk reported
`Alert script returned error code 5` on EVERY run -- while the alert itself had
been created perfectly. Nothing in that output said the TTPs alone were
missing.

The permission is a TheHive profile setting. There is nothing the add-on can
fix there; there is everything to gain from saying so precisely.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock

mocks = [
    'splunklib', 'splunklib.client', 'solnlib', 'solnlib.log',
    'solnlib.modular_input', 'solnlib.utils', 'ta_thehive_cortex_declare',
    'certifi', 'common', 'ta_logging', 'requests', 'requests.adapters',
    'requests.auth', 'urllib3', 'tomark',
]

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _isolation import temporary_mocks  # noqa: E402

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(APP_ROOT, 'TA-thehive-cortex', 'package', 'bin')
for p in (BIN,
          os.path.join(BIN, 'ta_thehive_cortex'),
          os.path.join(BIN, 'ta_thehive_cortex', 'libs')):
    if p not in sys.path:
        sys.path.insert(0, p)

with temporary_mocks(mocks):
    import post_creation  # noqa: E402


AUTHORIZATION_ERROR = (
    "AuthorizationError - You are not authorized to [Create several "
    "Procedures for Alert] POST /api/v1/alert/{alertId}/procedures, you "
    "don't have the permission manageProcedure"
)


class TestAttachProcedures(unittest.TestCase):

    def setUp(self):
        self.logger = MagicMock()
        self.endpoint = MagicMock()
        self.ttps = [{"patternId": "T1566", "occurDate": 1700000000000}]

    def _call(self):
        return post_creation.attach_procedures(
            endpoint=self.endpoint,
            object_id="~1234",
            ttps=self.ttps,
            logger_file=self.logger,
            url="https://thehive.example",
            context=lambda: "data={}",
        )

    def test_a_refused_permission_does_not_kill_the_action(self):
        self.endpoint.create_procedures.side_effect = Exception(AUTHORIZATION_ERROR)

        # No exception escapes: the alert exists, the action must not die
        self.assertIsNone(self._call())

    def test_a_refused_permission_names_the_permission(self):
        """A code 5 with no explanation is what this replaces."""
        self.endpoint.create_procedures.side_effect = Exception(AUTHORIZATION_ERROR)

        self._call()

        message = self.logger.error.call_args.kwargs["message"]
        self.assertIn("manageProcedure", message)
        self.assertIn("was created", message)
        self.assertEqual(self.logger.error.call_args.kwargs["id"], "133")

    def test_any_other_failure_is_reported_with_its_raw_error(self):
        """⚠️ Distinct from the permission case on purpose: one is a
        permission to grant, the other is anybody's guess."""
        self.endpoint.create_procedures.side_effect = Exception("connection reset")

        self.assertIsNone(self._call())

        self.assertEqual(self.logger.error.call_args.kwargs["id"], "134")
        self.assertIn("connection reset", self.logger.error.call_args.kwargs["message"])

    def test_success_is_still_reported_as_success(self):
        self.endpoint.create_procedures.return_value = [{"_id": "~9999"}]

        response = self._call()

        self.assertEqual(response, {"_id": "~9999"})
        self.logger.info.assert_called_once()
        self.logger.error.assert_not_called()

    def test_a_rejected_payload_is_still_an_error_not_an_exception(self):
        """The pre-existing path: TheHive answered, but not with an object."""
        self.endpoint.create_procedures.return_value = [{"type": "BadRequest"}]

        self._call()

        self.assertEqual(self.logger.error.call_args.kwargs["id"], "139")


if __name__ == '__main__':
    unittest.main()
