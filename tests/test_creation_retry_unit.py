"""Creating an object in TheHive, with retries -- and telling the truth after.

⚠️ Two defects lived in BOTH copies of this loop, and they compound into the
worst possible outcome: a creation that **succeeded** was reported as failed,
and then crashed the alert action.

* `if retry_count == max_retry:` tests how many attempts were made, not whether
  the creation worked. With the default `max_retry = 2`, an object created on
  the second attempt lands exactly on that condition.
* the same line formats `str(e)`, but Python 3 **deletes** the name bound by
  `except ... as e` when the block ends -- so it raises NameError.
"""

import os
import sys
import unittest

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(APP_ROOT, 'TA-thehive-cortex', 'package', 'bin')
for p in (BIN, os.path.join(BIN, 'ta_thehive_cortex')):
    if p not in sys.path:
        sys.path.insert(0, p)

from creation_retry import create_with_retry  # noqa: E402


class JournalDeTest:
    def __init__(self):
        self.lignes = []

    def warning(self, id="?", message=""):
        self.lignes.append(("warning", id, message))

    def error(self, id="?", message=""):
        self.lignes.append(("error", id, message))

    def identifiants(self, niveau=None):
        return [i for n, i, _ in self.lignes if niveau is None or n == niveau]


class ErreurDeService(Exception):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


IDS = {"duplicate": "122", "retry": "123", "exhausted": "125"}


def contexte():
    return "url=https://thehive.invalid, data=<payload>"


class Base(unittest.TestCase):
    def setUp(self):
        self.journal = JournalDeTest()

    def lancer(self, resultats, max_retry=2, ids=IDS):
        """`resultats` is what each successive attempt does."""
        appels = {"n": 0}

        def create():
            i = appels["n"]
            appels["n"] += 1
            r = resultats[i]
            if isinstance(r, Exception):
                raise r
            return r

        rendu = create_with_retry(create, max_retry, self.journal, ids, contexte)
        return rendu, appels["n"]


class UneCreationQuiFinitParReussir(Base):

    def test_reussite_du_premier_coup_ne_journalise_rien(self):
        rendu, appels = self.lancer([{"_id": "~1"}])
        self.assertEqual(rendu, {"_id": "~1"})
        self.assertEqual(appels, 1)
        self.assertEqual(self.journal.lignes, [])

    def test_reussite_a_la_DEUXIEME_tentative_n_est_pas_un_echec(self):
        # ⚠️ THE defect. max_retry=2, success on attempt 2 => retry_count == 2
        # in the old code => "creation has failed, after retries" logged as an
        # ERROR, on an object that exists. And then NameError on str(e).
        rendu, appels = self.lancer([ErreurDeService("boom"), {"_id": "~1"}])
        self.assertEqual(rendu, {"_id": "~1"})
        self.assertEqual(appels, 2)
        self.assertEqual(self.journal.identifiants("error"), [])
        self.assertEqual(self.journal.identifiants("warning"), ["123"])

    def test_reussite_a_la_derniere_tentative_autorisee(self):
        rendu, appels = self.lancer(
            [ErreurDeService("a"), ErreurDeService("b"), {"_id": "~1"}])
        self.assertEqual(rendu, {"_id": "~1"})
        self.assertEqual(appels, 3)  # max_retry + 1 attempts
        self.assertEqual(self.journal.identifiants("error"), [])


class UneCreationQuiEchoueVraiment(Base):

    def test_toutes_les_tentatives_echouent(self):
        rendu, appels = self.lancer([ErreurDeService("x")] * 3)
        self.assertIsNone(rendu)
        self.assertEqual(appels, 3)
        self.assertEqual(self.journal.identifiants("error"), ["125"])

    def test_le_message_final_porte_la_DERNIERE_erreur(self):
        # ⚠️ Not `str(e)` read after the except block, which is a NameError in
        # Python 3. The exception is bound outside the handler on purpose.
        self.lancer([ErreurDeService("premiere"), ErreurDeService("derniere"),
                     ErreurDeService("derniere")])
        final = [m for n, i, m in self.journal.lignes if n == "error"][0]
        self.assertIn("derniere", final)

    def test_le_nombre_de_reprises_est_dans_le_message(self):
        # The old message carried the literal "{max_retry}": an f-string
        # placeholder inside a NON-f string, so the number never appeared.
        self.lancer([ErreurDeService("x")] * 4, max_retry=3)
        final = [m for n, i, m in self.journal.lignes if n == "error"][0]
        self.assertIn("3 retries", final)
        self.assertNotIn("{max_retry}", final)


class LeCasDuDoublon(Base):

    def test_un_doublon_annonce_par_le_texte(self):
        self.lancer([ErreurDeService("Alert already exists"), {"_id": "~1"}])
        self.assertEqual(self.journal.identifiants("warning"), ["122"])

    def test_un_doublon_annonce_par_le_code_409(self):
        self.lancer([ErreurDeService("nope", status_code=409), {"_id": "~1"}])
        self.assertEqual(self.journal.identifiants("warning"), ["122"])

    def test_le_code_lu_sur_la_reponse_quand_il_n_est_pas_sur_l_erreur(self):
        class Reponse:
            status_code = 400

        e = Exception("nope")
        e.response = Reponse()
        self.lancer([e, {"_id": "~1"}])
        self.assertEqual(self.journal.identifiants("warning"), ["122"])

    def test_sans_identifiant_de_doublon_on_retombe_sur_celui_de_reprise(self):
        # The case helper has no dedicated duplicate identifier, and must not
        # crash for lack of one.
        self.lancer([ErreurDeService("already exists"), {"_id": "~1"}],
                    ids={"retry": "126", "exhausted": "127"})
        self.assertEqual(self.journal.identifiants("warning"), ["126"])


class LeContexteN_estCalculeQueSiOnJournalise(Base):

    def test_aucun_appel_quand_tout_va_bien(self):
        appels = {"n": 0}

        def contexte_compte():
            appels["n"] += 1
            return "ctx"

        create_with_retry(lambda: {"_id": "~1"}, 2, self.journal, IDS,
                          contexte_compte)
        # Serialising a payload nobody will read is a cost that only shows up
        # under load.
        self.assertEqual(appels["n"], 0)


if __name__ == "__main__":
    unittest.main()
