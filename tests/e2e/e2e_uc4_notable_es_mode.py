"""UC4 -- the ES notable path, which is exactly one thing: where sourceRef comes from.

Replays `docs/alert_actions_and_adaptive_responses.md` § UC4. The search is
the documented one, plus the `event_id` a notable carries.

⚠️ **This case does NOT create a real notable event.** Read
`modalert_thehive_common.py`: `es_mode` changes one decision and only one --
when the configured `unique_id_field` is absent from the row, the alert's
`sourceRef` is taken from `event_id` (the notable's identifier) instead of
from the search id. Everything else is the ordinary alert path, already
covered by UC1 and UC2.

Standing up a correlation search would therefore prove nothing more, and it
would write into the `notable` index -- which this campaign could not clean
up afterwards. A test that leaves rows behind in a production index is worse
than the coverage it buys. What it does instead is drive the *decision*: the
row carries an `event_id`, the configured unique id field is deliberately
absent, and the assertion is on the sourceRef TheHive ended up with.

⚠️ And the sourceRef is not cosmetic: rows sharing one are MERGED into a
single alert. Getting it wrong does not produce a visibly wrong alert, it
silently merges or splits alerts that should not be.
"""

import unittest

from . import _config
from ._case import CampagneE2E
from ._thehive import champs_personnalises

ACTION = "thehive_create_a_new_alert"

#: The documented UC4 search, plus the `event_id` an ES notable carries. Note
#: what is NOT here: any field called `unique`. That absence is the point.
RECHERCHE = """| makeresults
| eval other="account-12345", hostname="mycloud.aws.instance.corp"
| eval cert-alerted-on=now(), risk="Medium"
| eval event_id = "{event_id}", name = "{titre}"
"""


class TestUC4NotableEsMode(CampagneE2E):

    def test_le_sourceref_vient_de_l_event_id_du_notable(self):
        titre = f"{self.prefixe} Notable - adaptive response"
        event_id = f"{self.prefixe}_notable_event_id"
        recherche = RECHERCHE.format(titre=titre, event_id=event_id)

        nom = self.jouer(
            "uc4",
            recherche,
            ACTION,
            {
                "thehive_instance_id": self.nom_instance,
                "alert_mode": "es_mode",
                # Declared, and deliberately absent from the rows: that is the
                # condition under which es_mode reaches for `event_id`.
                "unique_id_field": "unique",
                "case_template": "",
                "type": "alert",
                "source": "splunk",
                "timestamp_field": "",
                "title": "name",
                "description": "name",
                "tags": "e2e,uc4",
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

        alertes = self.thehive.attendre_alertes(self.prefixe, 1, _config.DELAI_THEHIVE)
        self.assertEqual(1, len(alertes), "exactly one alert should have been created")
        alerte = alertes[0]

        self.assertEqual(
            event_id,
            alerte.get("sourceRef"),
            "in es_mode with the unique id field absent, sourceRef is the notable's event_id",
        )
        self.assertEqual(titre, alerte.get("title"))

        observables = {
            (obs.get("data"), obs.get("dataType"))
            for obs in self.thehive.attendre_observables_de_l_alerte(
                alerte["_id"], 2, _config.DELAI_THEHIVE
            )
        }
        self.assertEqual(
            {("account-12345", "other"), ("mycloud.aws.instance.corp", "hostname")},
            observables,
        )

        champs = champs_personnalises(alerte)
        self.assertEqual("Medium", champs.get("risk"))
        self.assertIsNotNone(champs.get("cert-alerted-on"))

        self.assert_journal_propre(nom)


if __name__ == "__main__":
    unittest.main()
