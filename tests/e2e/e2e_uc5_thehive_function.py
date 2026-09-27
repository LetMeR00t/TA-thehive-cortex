"""UC5 -- pushing events to a TheHive Function.

Replays `docs/alert_actions_and_adaptive_responses.md` § UC5, which the
documentation itself does not detail: "it's just pushing events to a custom
Function in TheHive".

The target is the Function `e2e-uc5-echo` (source: `uc5_echo_function.js`,
installed once by `python -m tests.e2e.uc5_function --install`, and left in
place). It turns the pushed events into ONE alert titled with the first
event's `name` -- so, unlike a bare "the action ran", this case can assert on
TheHive's side that the events actually ARRIVED and were understood.

⚠️ **This case skips unless `E2E_THEHIVE_FUNCTION` is set**, and says so.
Functions need a Platinum licence (the lab instance has one, 2026-09-27); what
used to make this case skip was simply that no Function existed --
`listFunction` was empty -- not a missing licence, as this file wrongly said
before. A test that quietly disappeared would leave UC5 looking covered;
skipping WITH THE REASON is the honest option when there is nothing to push to.
"""

import os
import unittest

from . import _config
from ._case import E2ECampaign

ACTION = "thehive_run_function"

SEARCH = """| makeresults
| eval other="account-12345", hostname="mycloud.aws.instance.corp"
| eval name = "{title}"
"""


def _configured_function():
    return os.environ.get("E2E_THEHIVE_FUNCTION")


class TestUC5TheHiveFunction(E2ECampaign):

    @unittest.skipUnless(
        _configured_function(),
        "no TheHive Function to push to: set E2E_THEHIVE_FUNCTION (e.g. e2e-uc5-echo, "
        "installed by `python -m tests.e2e.uc5_function --install`) to run this case",
    )
    def test_events_are_sent_to_the_function(self):
        title = f"{self.prefix} Function push"
        name = self.play(
            "uc5",
            SEARCH.format(title=title),
            ACTION,
            {
                "thehive_instance_id": self.instance_name,
                "name": _configured_function(),
            },
        )

        # The Function's side effect is the proof that the events arrived:
        # one alert, titled with the pushed `name`, tagged by the Function.
        # Without it, the only thing the add-on could be held to was "it
        # reported success" -- which an action that pushed nothing also does.
        alerts = self.thehive.wait_for_alerts(self.prefix, 1, _config.THEHIVE_TIMEOUT)
        self.assertEqual(
            1, len(alerts),
            f"the Function {_configured_function()!r} must have created exactly one "
            "alert from the pushed events")
        self.assertEqual(title, alerts[0].get("title"), "the pushed `name` must reach the Function")
        self.assertEqual("e2e-uc5-echo", alerts[0].get("type"))
        self.assertIn("uc5", alerts[0].get("tags") or [])

        self.assert_clean_log(name)

        rows = self.splunk.action_log(name)
        self.assertTrue(
            any("Invoking modular action" in row for row in rows),
            "the alert action must at least have been invoked",
        )


if __name__ == "__main__":
    unittest.main()
