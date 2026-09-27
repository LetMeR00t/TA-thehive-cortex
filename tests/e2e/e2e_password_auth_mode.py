"""#38: the `password` authentication mode, on its own account.

Every other case reuses the template's `api_key` account, so nothing watched
this path: the day it broke, the campaign stayed green.

Measured on TheHive 5.7.5 (scalligraph `BasicAuthSrv`): the `password` mode
sends HTTP Basic, and TheHive reads Basic as `user:password[:otp]`, splitting
on EVERY ':'. The lab account's password contains one, so this mode cannot
authenticate there -- the same credentials pass through `/api/v1/login`.

The contract asserted is therefore the one the add-on can keep whatever the
account looks like: either the alert is created, or the action says, in terms
of the AUTHENTICATION MODE (`TH111`), why it was refused -- never the bare
`TH110 AuthenticationError` that accuses a password the user knows is right.

⚠️ This case writes THEHIVE_USER/THEHIVE_PASSWORD into Splunk's credential
store, which the other cases avoid on purpose. The account carries the run
prefix and is deleted in `tearDownClass`, after a failure too; `purge` finds it
if the run is killed.
"""

import time
import unittest

from . import _config
from ._case import E2ECampaign

ACTION = "thehive_create_a_new_alert"

SEARCH = """| makeresults
| eval ip="1.2.3.4"
| eval name = "{title}", unique = "{unique}"
"""

#: The action log reaches `cim_modactions` through indexing: poll, never read once.
LOG_TIMEOUT = 180


class TestPasswordAuthenticationMode(E2ECampaign):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        template = cls.splunk.read_instance(_config.value("E2E_TEMPLATE_INSTANCE"))
        cls.password_account = f"{cls.prefix}_pwd_account"
        cls.password_instance = f"{cls.prefix}_pwd_instance"
        # Account first, instance second: the teardown walks the list
        # backwards, and an account cannot go while an instance points at it.
        cls.splunk.create_account(
            cls.password_account,
            _config.value("THEHIVE_USER"),
            _config.value("THEHIVE_PASSWORD"),
        )
        cls._splunk_objects.append(("account", cls.password_account))
        cls.splunk.create_instance(
            cls.password_instance, template, cls.password_account, "password"
        )
        cls._splunk_objects.append(("instance", cls.password_instance))

    def test_password_mode_creates_the_alert_or_names_the_mode(self):
        title = f"{self.prefix} password mode"
        name = self.play(
            "pwd",
            SEARCH.format(title=title, unique=f"{self.prefix}_pwd"),
            ACTION,
            {
                "thehive_instance_id": self.password_instance,
                "alert_mode": "regular_mode",
                "unique_id_field": "unique",
                "type": "alert",
                "source": "splunk",
                "title": "name",
                "description": "name",
                "tags": "e2e,password",
                "scope": "0",
                "severity": "2",
                "tlp": "2",
                "pap": "2",
                "description_results_enable": "0",
                "description_results_keep_observable": "0",
                "attach_results": "0",
                "attach_format": "0",
            },
        )

        rows = self._wait_for_log(name)
        self.assertTrue(rows, f"the alert action left no log line within {LOG_TIMEOUT}s")

        created = self.thehive.wait_for_alerts(self.prefix, 1, 30)
        if created:
            # The mode works for this account: the log must then be clean.
            self.assert_clean_log(name)
            return

        refusals = [row for row in rows if "TH111" in row]
        self.assertTrue(
            refusals,
            "TheHive refused the password mode and the action did not say so in "
            "terms of the mode (TH111); lines seen: "
            + str([row[:160] for row in rows if "ERROR" in row]),
        )
        self.assertIn("'password'", refusals[0], "TH111 must name the mode that was refused")
        self.assertFalse(
            [row for row in rows if "TH110" in row],
            "a refused authentication must not be reported as a connection error",
        )

    def _wait_for_log(self, search_name):
        deadline = time.time() + LOG_TIMEOUT
        while time.time() < deadline:
            rows = self.splunk.action_log(search_name)
            if any("ERROR" in row or "created" in row.lower() for row in rows):
                return rows
            time.sleep(10)
        return self.splunk.action_log(search_name)


if __name__ == "__main__":
    unittest.main()
