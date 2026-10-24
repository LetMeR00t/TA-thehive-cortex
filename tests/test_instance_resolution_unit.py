"""Resolving an instance must not be able to kill the Splunk process.

`getInstanceURL` and `getInstanceUsernameApiKey` called `sys.exit(30)` and
`sys.exit(31)` on an instance id they did not recognise. From a search command
that is not an error message -- it is the process going away, so the user sees
a search that stopped without saying why.

Coverage of these two functions was **0 %**, and for a structural reason worth
naming: every existing unit test mocks the whole `common` module, so nothing
could reach this code. Mocking a module wholesale makes all of it untestable.

The tests below build a `Settings` with `__init__` BYPASSED. That constructor
is 234 lines and talks to Splunk's configuration manager; going through it
would mean testing the connection, not the resolution.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock

mocks = [
    'splunklib', 'splunklib.client', 'solnlib', 'solnlib.log',
    'solnlib.modular_input', 'solnlib.utils', 'ta_thehive_cortex_declare',
    'splunk', 'splunk.Intersplunk', 'splunk.rest', 'globals', 'certifi',
    'requests', 'requests.adapters', 'requests.auth', 'requests.exceptions',
    'urllib3', 'urllib3.util', 'urllib3.util.retry', 'tomark',
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

# ⚠️ `common` itself is NOT mocked: it is what is under test. That single line
# is the difference between this file and every other one in the suite.
with temporary_mocks(mocks):
    import common


#: A plausible instance row, with no real host and no real credential (§2).
INSTANCE = {
    "host": "thehive.invalid",
    "port": "9000",
    "uri": "/",
    "username": "-",
    "password": "-",
    "organisation": "test-org",
}

TECHNIQUE = "/servicesNS/nobody/TA-thehive-cortex/thehive_cortex_instances/mon instance"


def settings_text(instances=None, match=None):
    """A Settings whose __init__ is bypassed: it connects to Splunk."""
    s = object.__new__(common.Settings)
    s.logger_file = MagicMock()
    s._instances = instances if instances is not None else {"connue": dict(INSTANCE)}
    s._id_to_name = match if match is not None else {}
    return s


class TestInstanceResolution(unittest.TestCase):

    def test_a_known_instance_returns_its_url(self):
        s = settings_text()
        self.assertEqual("https://thehive.invalid:9000", s.getInstanceURL("connue"))

    def test_root_uri_leaves_no_slash(self):
        """`uri = "/"` must collapse to nothing: the API library adds its own."""
        s = settings_text()
        self.assertFalse(s.getInstanceURL("connue").endswith("/"))

    def test_a_real_uri_is_kept(self):
        s = settings_text(instances={"connue": dict(INSTANCE, uri="/thehive")})
        self.assertEqual("https://thehive.invalid:9000/thehive", s.getInstanceURL("connue"))

    def test_technical_id_is_resolved(self):
        s = settings_text(match={TECHNIQUE: "connue"})
        self.assertEqual("https://thehive.invalid:9000", s.getInstanceURL(TECHNIQUE))

    def test_url_encoded_technical_id_is_resolved(self):
        """A space becomes %20 in the technical id. Both spellings must resolve.

        This is the variant nothing ever exercised: an instance whose NAME has
        a space is written one way in the configuration and another way in the
        URL, and only one of the two was ever tried by hand.
        """
        s = settings_text(match={TECHNIQUE.replace(" ", "%20"): "connue"})
        self.assertEqual(
            "https://thehive.invalid:9000",
            s.getInstanceURL(TECHNIQUE.replace(" ", "%20")),
        )

    def test_unknown_instance_raises_a_named_error(self):
        """⚠️ The heart of it: an unknown id must NOT end the process."""
        s = settings_text()
        with self.assertRaises(common.InstanceResolutionError) as ctx:
            s.getInstanceURL("jamais-configuree")
        self.assertIn("jamais-configuree", str(ctx.exception))

    def test_unknown_instance_also_raises_on_credentials(self):
        s = settings_text()
        with self.assertRaises(common.InstanceResolutionError):
            s.getInstanceUsernameApiKey("jamais-configuree")

    def test_credentials_of_a_known_instance_are_returned(self):
        s = settings_text()
        name_, secret = s.getInstanceUsernameApiKey("connue")
        self.assertEqual("-", name_)

    def test_instance_without_username_falls_back_to_the_dash(self):
        """No username at all: both fields fall back to the placeholder.

        This branch is what an instance authenticated by API key looks like
        before the account is joined -- it existed and nothing ever ran it.
        """
        without = {k: v for k, v in INSTANCE.items() if k not in ("username", "password")}
        s = settings_text(instances={"connue": without})
        name_, secret = s.getInstanceUsernameApiKey("connue")
        self.assertEqual(("-", "-"), (name_, secret))

    def test_instance_with_name_but_no_secret_returns_none(self):
        """A username without a secret must yield None, not the string "-".

        The distinction matters downstream: "-" is a value the client would
        try to authenticate with, None is the absence of one.
        """
        without = {k: v for k, v in INSTANCE.items() if k != "password"}
        s = settings_text(instances={"connue": without})
        name_, secret = s.getInstanceUsernameApiKey("connue")
        self.assertEqual("-", name_)
        self.assertIsNone(secret)

    def test_an_absent_setting_does_not_raise(self):
        """Distinct on purpose: a missing SETTING is not a missing INSTANCE.

        One is a hole in the configuration of something that exists; the other
        is a reference to something that does not. Collapsing the two would
        make an ordinary default look like a fatal error.
        """
        s = settings_text()
        self.assertIsNone(s.getInstanceSetting("connue", "reglage_absent"))


if __name__ == '__main__':
    unittest.main()
