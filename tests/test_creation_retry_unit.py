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


class RecordingLogger:
    def __init__(self):
        self.rows = []

    def warning(self, id="?", message=""):
        self.rows.append(("warning", id, message))

    def error(self, id="?", message=""):
        self.rows.append(("error", id, message))

    def ids(self, niveau=None):
        return [i for n, i, _ in self.rows if niveau is None or n == niveau]


class ServiceError(Exception):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


IDS = {"duplicate": "122", "retry": "123", "exhausted": "125"}


def context():
    return "url=https://thehive.invalid, data=<payload>"


class Base(unittest.TestCase):
    def setUp(self):
        self.recorder = RecordingLogger()

    def launch(self, results, max_retry=2, ids=IDS):
        """`results` is what each successive attempt does."""
        calls = {"n": 0}

        def create():
            i = calls["n"]
            calls["n"] += 1
            r = results[i]
            if isinstance(r, Exception):
                raise r
            return r

        rendu = create_with_retry(create, max_retry, self.recorder, ids, context)
        return rendu, calls["n"]


class ACreationThatEventuallySucceeds(Base):

    def test_reussite_du_premier_coup_ne_journalise_rien(self):
        rendu, calls = self.launch([{"_id": "~1"}])
        self.assertEqual(rendu, {"_id": "~1"})
        self.assertEqual(calls, 1)
        self.assertEqual(self.recorder.rows, [])

    def test_reussite_a_la_DEUXIEME_tentative_n_est_pas_un_echec(self):
        # ⚠️ THE defect. max_retry=2, success on attempt 2 => retry_count == 2
        # in the old code => "creation has failed, after retries" logged as an
        # ERROR, on an object that exists. And then NameError on str(e).
        rendu, calls = self.launch([ServiceError("boom"), {"_id": "~1"}])
        self.assertEqual(rendu, {"_id": "~1"})
        self.assertEqual(calls, 2)
        self.assertEqual(self.recorder.ids("error"), [])
        self.assertEqual(self.recorder.ids("warning"), ["123"])

    def test_reussite_a_la_derniere_tentative_autorisee(self):
        rendu, calls = self.launch(
            [ServiceError("a"), ServiceError("b"), {"_id": "~1"}])
        self.assertEqual(rendu, {"_id": "~1"})
        self.assertEqual(calls, 3)  # max_retry + 1 attempts
        self.assertEqual(self.recorder.ids("error"), [])


class ACreationThatTrulyFails(Base):

    def test_toutes_les_tentatives_echouent(self):
        rendu, calls = self.launch([ServiceError("x")] * 3)
        self.assertIsNone(rendu)
        self.assertEqual(calls, 3)
        self.assertEqual(self.recorder.ids("error"), ["125"])

    def test_le_message_final_porte_la_DERNIERE_erreur(self):
        # ⚠️ Not `str(e)` read after the except block, which is a NameError in
        # Python 3. The exception is bound outside the handler on purpose.
        self.launch([ServiceError("premiere"), ServiceError("derniere"),
                     ServiceError("derniere")])
        final = [m for n, i, m in self.recorder.rows if n == "error"][0]
        self.assertIn("derniere", final)

    def test_le_nombre_de_reprises_est_dans_le_message(self):
        # The old message carried the literal "{max_retry}": an f-string
        # placeholder inside a NON-f string, so the number never appeared.
        self.launch([ServiceError("x")] * 4, max_retry=3)
        final = [m for n, i, m in self.recorder.rows if n == "error"][0]
        self.assertIn("3 retries", final)
        self.assertNotIn("{max_retry}", final)


class TheDuplicateCase(Base):

    def test_un_doublon_annonce_par_le_texte(self):
        self.launch([ServiceError("Alert already exists"), {"_id": "~1"}])
        self.assertEqual(self.recorder.ids("warning"), ["122"])

    def test_un_doublon_annonce_par_le_code_409(self):
        self.launch([ServiceError("nope", status_code=409), {"_id": "~1"}])
        self.assertEqual(self.recorder.ids("warning"), ["122"])

    def test_le_code_lu_sur_la_reponse_quand_il_n_est_pas_sur_l_erreur(self):
        class Response:
            status_code = 400

        e = Exception("nope")
        e.response = Response()
        self.launch([e, {"_id": "~1"}])
        self.assertEqual(self.recorder.ids("warning"), ["122"])

    def test_sans_identifiant_de_doublon_on_retombe_sur_celui_de_reprise(self):
        # The case helper has no dedicated duplicate identifier, and must not
        # crash for lack of one.
        self.launch([ServiceError("already exists"), {"_id": "~1"}],
                    ids={"retry": "126", "exhausted": "127"})
        self.assertEqual(self.recorder.ids("warning"), ["126"])


class ContextIsBuiltOnlyWhenLogging(Base):

    def test_aucun_appel_quand_tout_va_bien(self):
        calls = {"n": 0}

        def contexte_compte():
            calls["n"] += 1
            return "ctx"

        create_with_retry(lambda: {"_id": "~1"}, 2, self.recorder, IDS,
                          contexte_compte)
        # Serialising a payload nobody will read is a cost that only shows up
        # under load.
        self.assertEqual(calls["n"], 0)


if __name__ == "__main__":
    unittest.main()
