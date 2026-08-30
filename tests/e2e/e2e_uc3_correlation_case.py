"""UC3 -- a correlation search, one case, and the reserved `th_*` overrides.

Replays `docs/alert_actions_and_adaptive_responses.md` § UC3. Two things only
this case exercises:

* the **case** action rather than the alert one -- a different creation path,
  86 % shared with the alert one but not 100 %;
* the reserved fields `th_severity`, `th_tlp`, `th_pap`, which override what
  the dialog was configured with. The dialog here deliberately says something
  else (severity Low, TLP WHITE, PAP WHITE) so that a passing assertion can
  only mean the search won -- with matching values, the test would pass even
  if the overrides were ignored entirely.

⚠️ `th_tlp="AMBER+STRICT"` is the value the documentation uses, and it maps to
TLP 3 -- a level that did not exist in TheHive 4. It is the interesting one.
"""

import unittest

from . import _config
from ._case import CampagneE2E
from ._thehive import champs_personnalises

ACTION = "thehive_create_a_new_case"

#: Verbatim from the documentation, with the title carrying the run prefix.
RECHERCHE = """| makeresults
| eval other="account-12345", hostname="mycloud.aws.instance.corp"
| eval cert-alerted-on=now(), risk="Medium", th_severity=4, th_tlp="AMBER+STRICT", th_pap="2"
| eval name = "{titre}", unique = "{unique}"
"""


class TestUC3UnSeulCas(CampagneE2E):

    def test_le_cas_arrive_et_les_champs_reserves_gagnent(self):
        titre = f"{self.prefixe} Correlation search - single case"
        recherche = RECHERCHE.format(titre=titre, unique=f"{self.prefixe}_uc3")

        nom = self.jouer(
            "uc3",
            recherche,
            ACTION,
            {
                "thehive_instance_id": self.nom_instance,
                "case_mode": "regular_mode",
                "unique_id_field": "unique",
                "case_template": "",
                "source": "splunk",
                "timestamp_field": "",
                "title": "name",
                "description": "name",
                "tags": "e2e,uc3",
                "scope": "0",
                # Deliberately NOT what the search asks for: the point is to
                # watch `th_severity` / `th_tlp` / `th_pap` win.
                "severity": "1",
                "tlp": "0",
                "pap": "0",
                "description_results_enable": "0",
                "description_results_keep_observable": "0",
                "attach_results": "0",
                "attach_format": "0",
            },
        )

        cas = self.thehive.attendre_cas(self.prefixe, 1, _config.DELAI_THEHIVE)
        self.assertEqual(1, len(cas), "exactly one case should have been created")
        le_cas = cas[0]

        self.assertEqual(titre, le_cas.get("title"))
        self.assertEqual(4, le_cas.get("severity"), "th_severity=4 must beat the dialog's 1")
        self.assertEqual(3, le_cas.get("tlp"), 'th_tlp="AMBER+STRICT" must beat the dialog\'s WHITE')
        self.assertEqual(2, le_cas.get("pap"), 'th_pap="2" must beat the dialog\'s WHITE')

        observables = {
            (obs.get("data"), obs.get("dataType"))
            for obs in self.thehive.attendre_observables_du_cas(
                le_cas["_id"], 2, _config.DELAI_THEHIVE
            )
        }
        self.assertEqual(
            {("account-12345", "other"), ("mycloud.aws.instance.corp", "hostname")},
            observables,
            "both fields are declared in thehive_datatypes.csv and must keep their type",
        )

        champs = champs_personnalises(le_cas)
        self.assertEqual("Medium", champs.get("risk"))
        self.assertIsNotNone(champs.get("cert-alerted-on"))

        # The documentation states it plainly: a correlation search cannot
        # reach its own TTPs, so none is expected here. Asserting the absence
        # keeps that documented limitation from silently becoming a defect.
        self.assertEqual(
            [], self.thehive.procedures_du_cas(le_cas["_id"]),
            "UC3 documents that no TTP can come from a correlation search",
        )

        self.assert_journal_propre(nom)


if __name__ == "__main__":
    unittest.main()
