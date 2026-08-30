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
from ._case import CampagneE2E

ACTION = "thehive_run_function"

RECHERCHE = """| makeresults
| eval other="account-12345", hostname="mycloud.aws.instance.corp"
| eval name = "{titre}"
"""


def _fonction_configuree():
    return os.environ.get("E2E_THEHIVE_FUNCTION")


class TestUC5FonctionTheHive(CampagneE2E):

    @unittest.skipUnless(
        _fonction_configuree(),
        "no TheHive Function to push to: Functions are a licensed feature and "
        "listFunction is empty on this instance; set E2E_THEHIVE_FUNCTION to run this case",
    )
    def test_les_evenements_partent_vers_la_fonction(self):
        titre = f"{self.prefixe} Function push"
        nom = self.jouer(
            "uc5",
            RECHERCHE.format(titre=titre),
            ACTION,
            {
                "thehive_instance_id": self.nom_instance,
                "name": _fonction_configuree(),
            },
        )

        # ⚠️ A Function leaves no alert and no case behind: the only thing the
        # add-on can be held to here is that it reported success and logged no
        # error. Asserting on TheHive's side would need the Function's own
        # side effect, which is specific to whatever it was written to do.
        self.assert_journal_propre(nom)

        lignes = self.splunk.journal_de_l_action(nom)
        self.assertTrue(
            any("Invoking modular action" in ligne for ligne in lignes),
            "the alert action must at least have been invoked",
        )


if __name__ == "__main__":
    unittest.main()
