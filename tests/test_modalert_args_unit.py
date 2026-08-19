"""Reading the alert action form -- and the two defaulting rules in it.

⚠️ These ~110 lines existed twice, and the pattern
`helper.get_param(x) if helper.get_param(x) else default` was written out about
twenty-five times per copy. Two rules hide inside that shape, and they are not
interchangeable:

* `if value`             -- an EMPTY string falls back to the default
* `if value is not None` -- an empty string is KEPT

Written by hand fifty times, nothing tells you which one a given field uses.
Named, it becomes visible -- and testable.
"""

import os
import sys
import time
import unittest

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(APP_ROOT, 'TA-thehive-cortex', 'package', 'bin')
for p in (BIN, os.path.join(BIN, 'ta_thehive_cortex')):
    if p not in sys.path:
        sys.path.insert(0, p)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _isolation import mocks_temporaires  # noqa: E402

import modalert_args  # noqa: E402
from modalert_args import common_args, entier, etiquettes, horodatage, si_absent, si_vide  # noqa: E402


class HelperDeTest:
    """A faithful stand-in: it answers only the names it was given, so a typo
    in a parameter name shows up as KeyError instead of a MagicMock."""

    def __init__(self, params=None, globaux=None):
        self.params = params or {}
        self.globaux = globaux or {}
        self.appels = []

    def get_param(self, nom):
        self.appels.append(nom)
        return self.params.get(nom)

    def get_global_setting(self, nom):
        return self.globaux.get(nom)


class JournalDeTest:
    def __init__(self):
        self.lignes = []

    def debug(self, id="?", message=""):
        self.lignes.append((id, message))


FORMULAIRE = {
    "unique_id_field": "src", "case_template": "tmpl", "source": "es",
    "timestamp_field": "", "title": "Un titre", "description": "Une description",
    "tags": "a,b,a", "scope": "0", "severity": "3", "tlp": "1", "pap": "0",
    "description_results_enable": "1", "description_results_keep_observable": "0",
    "attach_results": "2", "attach_format": "1",
}


class LesDeuxReglesDeDefaut(unittest.TestCase):

    def test_si_vide_remplace_la_chaine_vide(self):
        self.assertEqual(si_vide("", "defaut"), "defaut")
        self.assertEqual(si_vide(None, "defaut"), "defaut")
        self.assertEqual(si_vide("valeur", "defaut"), "valeur")

    def test_si_absent_GARDE_la_chaine_vide(self):
        # ⚠️ The whole difference. A global setting deliberately left empty is
        # a value, not an absence.
        self.assertEqual(si_absent("", "defaut"), "")
        self.assertEqual(si_absent(None, "defaut"), "defaut")

    def test_entier_ne_convertit_que_ce_qui_existe(self):
        self.assertEqual(entier("3", 2), 3)
        self.assertEqual(entier(None, 2), 2)
        # ⚠️ "0" is falsy as a string but is NOT absent: it must survive.
        self.assertEqual(entier("0", 2), 0)


class LesEtiquettes(unittest.TestCase):

    def test_les_doublons_partent_et_l_ordre_reste(self):
        self.assertEqual(etiquettes("b,a,b,c"), ["b", "a", "c"])

    def test_une_valeur_vide_donne_une_liste_vide(self):
        self.assertEqual(etiquettes(""), [])
        self.assertEqual(etiquettes(None), [])


class L_horodatage(unittest.TestCase):

    def test_sans_champ_c_est_maintenant_en_millisecondes(self):
        avant = int(time.time() * 1000)
        valeur = horodatage("")
        self.assertGreaterEqual(valeur, avant)

    def test_une_epoque_a_dix_chiffres_passe_en_millisecondes(self):
        self.assertEqual(horodatage("1700000000"), 1700000000000)

    def test_tout_le_reste_ressort_TEL_QUEL(self):
        # ⚠️ Preserved on purpose, rough edge included: a date like
        # "2026-01-01" comes back as a string and blows up in whoever converts
        # it. Fixing that belongs to the parse_events work; this module must
        # not change behaviour while it removes duplication.
        self.assertEqual(horodatage("2026-01-01"), "2026-01-01")
        self.assertEqual(horodatage("1700000000000"), "1700000000000")


class L_assemblageComplet(unittest.TestCase):

    def setUp(self):
        self.journal = JournalDeTest()

    def construire(self, **remplacements):
        params = dict(FORMULAIRE)
        params.update(remplacements)
        self.helper = HelperDeTest(params, {})
        return common_args(self.helper, self.journal)

    def test_les_champs_du_formulaire(self):
        args = self.construire()
        self.assertEqual(args["unique_id_field"], "src")
        self.assertEqual(args["caseTemplate"], "tmpl")
        self.assertEqual(args["source"], "es")
        self.assertEqual(args["title"], "Un titre")
        self.assertEqual(args["tags"], ["a", "b"])
        self.assertEqual(args["severity"], 3)
        self.assertEqual(args["tlp"], 1)
        self.assertEqual(args["pap"], 0)
        self.assertEqual(args["attach_results"], 2)
        self.assertEqual(args["attach_format"], 1)

    def test_les_defauts_quand_le_formulaire_est_vide(self):
        args = self.construire(unique_id_field="", case_template="", source="",
                               title="", description="", tags="",
                               severity=None, tlp=None, pap=None)
        self.assertEqual(args["unique_id_field"], "oneEvent")
        self.assertIsNone(args["caseTemplate"])
        self.assertEqual(args["source"], "splunk")
        self.assertIsNone(args["title"])
        self.assertEqual(args["description"], "No description provided")
        self.assertEqual(args["tags"], [])
        self.assertEqual((args["severity"], args["tlp"], args["pap"]), (2, 2, 2))

    def test_scope_est_VRAI_quand_le_champ_vaut_zero(self):
        # Inverted on purpose in the form, and easy to get backwards.
        self.assertTrue(self.construire(scope="0")["scope"])
        self.assertFalse(self.construire(scope="1")["scope"])

    def test_les_antislashs_sont_convertis_quand_c_est_active(self):
        args = self.construire(description="ligne1\\nligne2")
        self.assertEqual(args["description"], "ligne1\nligne2")

    def test_ils_ne_le_sont_pas_quand_c_est_desactive(self):
        self.helper = HelperDeTest(
            dict(FORMULAIRE, description="ligne1\\nligne2"),
            {"splunk_sanitize_backslashes": "DISABLED"})
        args = common_args(self.helper, self.journal)
        self.assertEqual(args["description"], "ligne1\\nligne2")

    def test_les_reglages_globaux_ont_leurs_defauts(self):
        args = self.construire()
        self.assertEqual(args["splunk_sanitize_backslashes"], "ENABLED")
        self.assertEqual(args["splunk_es_alerts_index"], "summary")

    def test_les_deux_drapeaux_booleens(self):
        args = self.construire(description_results_enable="1",
                               description_results_keep_observable="1")
        self.assertTrue(args["description_results_enable"])
        self.assertTrue(args["description_results_keep_observable"])

    def test_le_scope_est_trace(self):
        self.construire()
        self.assertEqual([id for id, _ in self.journal.lignes], ["50"])

    def test_chaque_parametre_n_est_lu_qu_UNE_fois(self):
        # ⚠️ The duplicated pattern called get_param TWICE per field, about
        # twenty-five times over. Not a correctness bug -- a cost nobody chose.
        self.construire()
        doubles = {n for n in self.helper.appels
                   if self.helper.appels.count(n) > 1}
        self.assertEqual(doubles, {"scope"},
                         "only `scope` is read twice, for its own debug line")


class LesDeuxAppelantsPartagentLAssemblage(unittest.TestCase):

    def test_aucun_helper_ne_reconstruit_les_arguments_communs(self):
        for nom in ("modalert_thehive_create_a_new_case_helper.py",
                    "modalert_thehive_create_a_new_alert_helper.py"):
            with open(os.path.join(BIN, "ta_thehive_cortex", nom),
                      encoding="utf-8") as f:
                source = f.read()
            with self.subTest(helper=nom):
                self.assertIn("common_args(helper, logger_file)", source)
                self.assertNotIn('alert_args["severity"]', source)
                self.assertNotIn('alert_args["tlp"]', source)


class L_amorcageDesInstances(unittest.TestCase):
    """⚠️ La fonction que 123 tests verts n'exécutaient pas.

    `prepare_instances` portait `from modalert_thehive_common import
    create_thehive_instance` — la fonction vit dans `thehive`. C'est un
    ImportError sur la première ligne utile des DEUX actions de création, et la
    suite ne pouvait pas le voir : aucun test n'entrait dans cette fonction.

    Un test prouve les chemins qu'il PARCOURT. Celui-ci parcourt l'import.
    """

    def test_la_fonction_s_execute_vraiment(self):
        from unittest.mock import MagicMock

        helper = HelperDeTest({"thehive_instance_id": "local,distant"})
        helper.log_info = lambda m: None
        helper.log_debug = lambda m: None
        helper.set_log_level = lambda n: None
        helper.log_level = "INFO"
        helper.settings = {"sessionKey": "(SANITIZED)"}
        helper._logger = MagicMock()
        helper.exec_id = "abcd1234"

        faux_globals = MagicMock()
        fabriquees = []

        def fausse_fabrique(instance_id, settings, logger, acronym, exec_id):
            fabriquees.append((instance_id, acronym))
            return ("thehive", "conf", "defaults", "logger", instance_id)

        # ⚠️ On remplace les deux modules que la fonction importe PARESSEUSEMENT,
        # donc l'import a bien lieu — c'est lui qu'on teste.
        faux_thehive = MagicMock()
        faux_thehive.create_thehive_instance = fausse_fabrique
        with mocks_temporaires(["globals", "thehive"],
                               {"globals": faux_globals, "thehive": faux_thehive}):
            instances = modalert_args.prepare_instances(helper, acronym="THCC")

        self.assertEqual(len(instances), 2)
        self.assertEqual(fabriquees, [("local", "THCC"), ("distant", "THCC")])
        faux_globals.initialize_globals.assert_called_once()

    def test_l_acronyme_est_tisse_dans_les_deux_prefixes(self):
        from unittest.mock import MagicMock

        traces = []
        helper = HelperDeTest({"thehive_instance_id": "local"})
        helper.log_info = lambda m: traces.append(m)
        helper.log_debug = lambda m: traces.append(m)
        helper.set_log_level = lambda n: None
        helper.log_level = "DEBUG"
        helper.settings = {}
        helper._logger = MagicMock()
        helper.exec_id = "z"

        faux_thehive = MagicMock()
        faux_thehive.create_thehive_instance = lambda **k: ("t", "c", "d", "l", "i")
        with mocks_temporaires(["globals", "thehive"],
                               {"globals": MagicMock(), "thehive": faux_thehive}):
            modalert_args.prepare_instances(helper, acronym="THCA")

        self.assertTrue(any("[CAA-THCA-35]" in m for m in traces))
        self.assertTrue(any("[CAA-THCA-40]" in m for m in traces))


if __name__ == "__main__":
    unittest.main()
