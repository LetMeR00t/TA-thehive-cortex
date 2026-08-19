"""The file that carries Splunk search results to TheHive.

⚠️ This code existed **twice**, ~190 lines each, in the case and the alert
helpers -- 13 divergent lines out of 195, and the same log identifiers on both
sides. A `[141]` in production designated two places at once.

Nothing here is mocked but the logger: the tests write real gzip CSV files and
read back what the builder produced. The question asked is "what is in the
file", and a mock cannot answer that.
"""

import csv
import gzip
import json
import os
import shutil
import sys
import tempfile
import unittest

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(APP_ROOT, 'TA-thehive-cortex', 'package', 'bin')
for p in (BIN, os.path.join(BIN, 'ta_thehive_cortex')):
    if p not in sys.path:
        sys.path.insert(0, p)

import attachment_builder  # noqa: E402
from attachment_builder import AttachmentError, build_attachment  # noqa: E402


class JournalDeTest:
    """Records what was logged. A real object, not a MagicMock: an assertion
    against a mock's repr is an assertion that cannot fail."""

    def __init__(self):
        self.lignes = []

    def _note(self, niveau, id, message):
        self.lignes.append((niveau, id, message))

    def debug(self, id="?", message=""):
        self._note("debug", id, message)

    def info(self, id="?", message=""):
        self._note("info", id, message)

    def warn(self, id="?", message=""):
        self._note("warn", id, message)

    def error(self, id="?", message=""):
        self._note("error", id, message)

    def identifiants(self):
        return [id for _, id, _ in self.lignes]


ENTETES = ["_time", "host", "count"]
LIGNES = [["1700000000", "srv-01", "3"], ["1700000060", "srv-02", "7"]]


class Base(unittest.TestCase):

    def setUp(self):
        self.journal = JournalDeTest()
        self.atelier = tempfile.mkdtemp(prefix="thc_test_")
        self.resultats = os.path.join(self.atelier, "results_1234_5.csv.gz")
        with gzip.open(self.resultats, "wt", newline="") as f:
            w = csv.writer(f)
            w.writerow(ENTETES)
            w.writerows(LIGNES)
        self.nettoyer = [self.atelier]

    def tearDown(self):
        for d in self.nettoyer:
            shutil.rmtree(d, ignore_errors=True)

    def construire(self, attach_results=1, attach_format=0, prefix="events_",
                   object_id="~123~456"):
        tmp, chemin = build_attachment(
            results_file=self.resultats,
            attach_results=attach_results,
            attach_format=attach_format,
            attachment_prefix=prefix,
            object_id=object_id,
            logger_file=self.journal,
        )
        self.nettoyer.append(tmp)
        return tmp, chemin


class LesTroisModes(Base):

    def test_mode_1_recopie_le_gzip_sans_le_toucher(self):
        _, chemin = self.construire(attach_results=1)
        self.assertTrue(chemin.endswith(".csv.gz"))
        with gzip.open(chemin, "rt") as f:
            self.assertEqual(list(csv.reader(f)), [ENTETES] + LIGNES)

    def test_mode_2_produit_un_csv_lisible(self):
        _, chemin = self.construire(attach_results=2)
        self.assertTrue(chemin.endswith(".csv"))
        with open(chemin, newline="") as f:
            self.assertEqual(list(csv.reader(f)), [ENTETES] + LIGNES)

    def test_mode_3_produit_un_json_de_dictionnaires(self):
        _, chemin = self.construire(attach_results=3)
        self.assertTrue(chemin.endswith(".json"))
        with open(chemin) as f:
            charge = json.load(f)
        self.assertEqual(charge, [dict(zip(ENTETES, l)) for l in LIGNES])

    def test_mode_3_avec_une_seule_ligne_ecrit_un_OBJET_pas_un_tableau(self):
        # ⚠️ Inconsistent, and preserved on purpose: every downstream consumer
        # written against the current shape would break silently otherwise.
        with gzip.open(self.resultats, "wt", newline="") as f:
            w = csv.writer(f)
            w.writerow(ENTETES)
            w.writerow(LIGNES[0])
        _, chemin = self.construire(attach_results=3)
        with open(chemin) as f:
            self.assertEqual(json.load(f), dict(zip(ENTETES, LIGNES[0])))

    def test_un_mode_inconnu_est_nomme_au_lieu_de_planter_plus_loin(self):
        # Before: fell through the if/elif chain and died on open(None, "rb").
        with self.assertRaises(AttachmentError) as ctx:
            self.construire(attach_results=7)
        self.assertIn("7", str(ctx.exception))


class LesQuatreNomsDeFichier(Base):

    def test_format_0_prefixe_plus_identifiant_sans_tilde(self):
        _, chemin = self.construire(attach_format=0, prefix="events_")
        self.assertEqual(os.path.basename(chemin), "events_123456.csv.gz")

    def test_format_1_identifiant_seul(self):
        _, chemin = self.construire(attach_format=1)
        self.assertEqual(os.path.basename(chemin), "123456.csv.gz")

    def test_format_2_prefixe_plus_sha256(self):
        _, chemin = self.construire(attach_format=2, prefix="ev_")
        nom = os.path.basename(chemin)
        self.assertTrue(nom.startswith("ev_"))
        self.assertEqual(len(nom), len("ev_") + 64 + len(".csv.gz"))

    def test_format_3_sha256_seul(self):
        _, chemin = self.construire(attach_format=3)
        self.assertEqual(len(os.path.basename(chemin)), 64 + len(".csv.gz"))

    def test_le_sha256_est_celui_du_CONTENU_produit(self):
        import hashlib
        _, chemin = self.construire(attach_results=2, attach_format=3)
        with open(chemin, "rb") as f:
            attendu = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(os.path.basename(chemin), attendu + ".csv")

    def test_un_format_inconnu_a_son_PROPRE_identifiant_de_log(self):
        # ⚠️ This branch used to log id="141", already taken by the
        # results-file trace a hundred lines above -- in BOTH helpers.
        with self.assertRaises(AttachmentError):
            self.construire(attach_format=9)
        self.assertIn("146", self.journal.identifiants())
        self.assertNotIn("141", [id for niv, id, _ in self.journal.lignes
                                 if niv == "error"])


class CeQuiTombeMal(Base):

    def test_un_fichier_de_resultats_illisible_est_nomme_et_non_subi(self):
        # Before: headers stayed None and the failure surfaced as a TypeError
        # inside csv.writerow -- blaming the writer for a read that had already
        # failed and been logged.
        with open(self.resultats, "wb") as f:
            f.write(b"ceci n'est pas du gzip")
        with self.assertRaises(AttachmentError):
            self.construire(attach_results=2)
        self.assertIn("148", self.journal.identifiants())

    def test_chaque_appel_a_son_propre_repertoire(self):
        # ⚠️ The system temp dir is shared by every alert action worker; a
        # fixed file name collided between overlapping runs.
        tmp1, _ = self.construire()
        tmp2, _ = self.construire()
        self.assertNotEqual(tmp1, tmp2)
        self.assertTrue(os.path.isdir(tmp1) and os.path.isdir(tmp2))

    def test_le_repertoire_survit_a_l_appel(self):
        # The caller uploads FROM it, then removes it. Cleaning up here would
        # delete the file before it is read.
        tmp, chemin = self.construire()
        self.assertTrue(os.path.isfile(chemin))
        self.assertTrue(chemin.startswith(tmp))


class LesDeuxAppelantsPartagentLeMemeCode(unittest.TestCase):
    """The point of the ticket: one implementation, not two."""

    def test_les_deux_helpers_appellent_le_constructeur_partage(self):
        for nom in ("modalert_thehive_create_a_new_case_helper.py",
                    "modalert_thehive_create_a_new_alert_helper.py"):
            chemin = os.path.join(BIN, "ta_thehive_cortex", nom)
            with open(chemin, encoding="utf-8") as f:
                source = f.read()
            with self.subTest(helper=nom):
                self.assertIn("build_attachment(", source)
                # And none of the machinery it replaced is left behind.
                for reste in ("tempfile.mkdtemp", "gzip.open", "hashlib.sha256",
                              "csv.writer", "os.rename"):
                    self.assertNotIn(reste, source)


if __name__ == "__main__":
    unittest.main()
