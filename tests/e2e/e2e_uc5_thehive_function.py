"""UC5 -- pushing events to a TheHive Function.

Replays `docs/alert_actions_and_adaptive_responses.md` § UC5, which the
documentation itself does not detail: "it's just pushing events to a custom
Function in TheHive".

⚠️ **This case skips unless a Function exists**, and says so. Functions are a
licensed TheHive feature; measured on the lab instance, `listFunction`
returns an empty list, so there is nothing to push to. A test that quietly
disappeared here would leave UC5 looking covered; a test that failed would
blame the add-on for a licence it cannot buy. Skipping WITH THE REASON is the
only honest third option.

Set `E2E_THEHIVE_FUNCTION` to the function name to run it.
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
        "no TheHive Function to push to: Functions are a licensed feature and "
        "listFunction is empty on this instance; set E2E_THEHIVE_FUNCTION to run this case",
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

        # ⚠️ A Function leaves no alert and no case behind: the only thing the
        # add-on can be held to here is that it reported success and logged no
        # error. Asserting on TheHive's side would need the Function's own
        # side effect, which is specific to whatever it was written to do.
        self.assert_clean_log(name)

        rows = self.splunk.action_log(name)
        self.assertTrue(
            any("Invoking modular action" in row for row in rows),
            "the alert action must at least have been invoked",
        )


if __name__ == "__main__":
    unittest.main()
