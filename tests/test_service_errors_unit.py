"""Reading what TheHive said when a call failed.

⚠️ These six lines were pasted **three times** -- case creation retry, the
observables loop of the case helper, and the "Add observables" alert action --
comment included. A subtle rule copied three times is a rule that will
disagree with itself: the day TheHive adds a status code, two of the three get
updated.
"""

import os
import sys
import unittest

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(APP_ROOT, 'TA-thehive-cortex', 'package', 'bin')
for p in (BIN, os.path.join(BIN, 'ta_thehive_cortex')):
    if p not in sys.path:
        sys.path.insert(0, p)

from service_errors import is_duplicate, response_detail, status_code  # noqa: E402


class Response:
    def __init__(self, code=None, text=""):
        self.status_code = code
        self.text = text


class UnreadableResponse:
    status_code = 500

    @property
    def text(self):
        raise RuntimeError("le corps n'est pas lisible")


class StatusCode(unittest.TestCase):

    def test_porte_par_l_erreur(self):
        e = Exception("x")
        e.status_code = 409
        self.assertEqual(status_code(e), 409)

    def test_porte_par_la_reponse(self):
        e = Exception("x")
        e.response = Response(400)
        self.assertEqual(status_code(e), 400)

    def test_absent_des_deux(self):
        self.assertIsNone(status_code(Exception("x")))


class DuplicateDetection(unittest.TestCase):

    def test_par_le_texte_quelle_que_soit_la_casse(self):
        self.assertTrue(is_duplicate(Exception("Alert ALREADY EXISTS")))
        self.assertTrue(is_duplicate(Exception("Duplicate found")))

    def test_par_le_code(self):
        for code in (400, 409):
            with self.subTest(code=code):
                e = Exception("nope")
                e.status_code = code
                self.assertTrue(is_duplicate(e))

    def test_une_vraie_erreur_n_est_pas_un_doublon(self):
        e = Exception("internal server error")
        e.status_code = 500
        self.assertFalse(is_duplicate(e))

    def test_400_est_traite_comme_un_doublon_meme_sans_texte(self):
        # ⚠️ Broad, and preserved deliberately: a malformed payload also
        # answers 400. Narrowing it is a behaviour change of its own.
        e = Exception("")
        e.status_code = 400
        self.assertTrue(is_duplicate(e))


class ResponseDetail(unittest.TestCase):

    def test_le_corps_est_ajoute_quand_il_existe(self):
        e = Exception("x")
        e.response = Response(500, "details du serveur")
        self.assertEqual(response_detail(e), " | Response: details du serveur")

    def test_rien_quand_il_n_y_a_pas_de_reponse(self):
        self.assertEqual(response_detail(Exception("x")), "")

    def test_un_corps_illisible_ne_remplace_pas_la_vraie_erreur(self):
        # This only ever ENRICHES a message that is being logged anyway.
        e = Exception("x")
        e.response = UnreadableResponse()
        self.assertEqual(response_detail(e), "")


class TheThreeSitesConverge(unittest.TestCase):

    def test_plus_aucune_copie_de_la_regle(self):
        folder = os.path.join(BIN, "ta_thehive_cortex")
        for nom in sorted(os.listdir(folder)):
            if not nom.endswith(".py") or nom == "service_errors.py":
                continue
            with open(os.path.join(folder, nom), encoding="utf-8") as f:
                source = f.read()
            with self.subTest(fichier=nom):
                self.assertNotIn('"already exists" in', source)
                self.assertNotIn("is_duplicate = ", source)


if __name__ == "__main__":
    unittest.main()
