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
import sys
import tempfile
import unittest
import unittest.mock

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(APP_ROOT, 'TA-thehive-cortex', 'package', 'bin')
for p in (BIN, os.path.join(BIN, 'ta_thehive_cortex')):
    if p not in sys.path:
        sys.path.insert(0, p)

import attachment_builder  # noqa: E402
from attachment_builder import AttachmentError, build_attachment  # noqa: E402
from _isolation import remove_tree  # noqa: E402


class RecordingLogger:
    """Records what was logged. A real object, not a MagicMock: an assertion
    against a mock's repr is an assertion that cannot fail."""

    def __init__(self):
        self.rows = []

    def _note(self, niveau, id, message):
        self.rows.append((niveau, id, message))

    def debug(self, id="?", message=""):
        self._note("debug", id, message)

    def info(self, id="?", message=""):
        self._note("info", id, message)

    def warn(self, id="?", message=""):
        self._note("warn", id, message)

    def error(self, id="?", message=""):
        self._note("error", id, message)

    def ids(self):
        return [id for _, id, _ in self.rows]


ENTETES = ["_time", "host", "count"]
LIGNES = [["1700000000", "srv-01", "3"], ["1700000060", "srv-02", "7"]]


class Base(unittest.TestCase):

    def setUp(self):
        self.recorder = RecordingLogger()
        self.workshop = tempfile.mkdtemp(prefix="thc_test_")
        self.results = os.path.join(self.workshop, "results_1234_5.csv.gz")
        with gzip.open(self.results, "wt", newline="") as f:
            w = csv.writer(f)
            w.writerow(ENTETES)
            w.writerows(LIGNES)
        self.to_clean = [self.workshop]

    def tearDown(self):
        for d in self.to_clean:
            remove_tree(d)

    def build(self, attach_results=1, attach_format=0, prefix="events_",
                   object_id="~123~456"):
        tmp, path = build_attachment(
            results_file=self.results,
            attach_results=attach_results,
            attach_format=attach_format,
            attachment_prefix=prefix,
            object_id=object_id,
            logger_file=self.recorder,
        )
        self.to_clean.append(tmp)
        return tmp, path


class TheThreeModes(Base):

    def test_mode_1_recopie_le_gzip_sans_le_toucher(self):
        _, path = self.build(attach_results=1)
        self.assertTrue(path.endswith(".csv.gz"))
        with gzip.open(path, "rt") as f:
            self.assertEqual(list(csv.reader(f)), [ENTETES] + LIGNES)

    def test_mode_2_produit_un_csv_lisible(self):
        _, path = self.build(attach_results=2)
        self.assertTrue(path.endswith(".csv"))
        with open(path, newline="") as f:
            self.assertEqual(list(csv.reader(f)), [ENTETES] + LIGNES)

    def test_mode_3_produit_un_json_de_dictionnaires(self):
        _, path = self.build(attach_results=3)
        self.assertTrue(path.endswith(".json"))
        with open(path) as f:
            payload = json.load(f)
        self.assertEqual(payload, [dict(zip(ENTETES, l)) for l in LIGNES])

    def test_mode_3_avec_une_seule_ligne_ecrit_un_OBJET_pas_un_tableau(self):
        # ⚠️ Inconsistent, and preserved on purpose: every downstream consumer
        # written against the current shape would break silently otherwise.
        with gzip.open(self.results, "wt", newline="") as f:
            w = csv.writer(f)
            w.writerow(ENTETES)
            w.writerow(LIGNES[0])
        _, path = self.build(attach_results=3)
        with open(path) as f:
            self.assertEqual(json.load(f), dict(zip(ENTETES, LIGNES[0])))

    def test_un_mode_inconnu_est_nomme_au_lieu_de_planter_plus_loin(self):
        # Before: fell through the if/elif chain and died on open(None, "rb").
        with self.assertRaises(AttachmentError) as ctx:
            self.build(attach_results=7)
        self.assertIn("7", str(ctx.exception))


class TheFourFileNames(Base):

    def test_format_0_prefixe_plus_identifiant_sans_tilde(self):
        _, path = self.build(attach_format=0, prefix="events_")
        self.assertEqual(os.path.basename(path), "events_123456.csv.gz")

    def test_format_1_identifiant_seul(self):
        _, path = self.build(attach_format=1)
        self.assertEqual(os.path.basename(path), "123456.csv.gz")

    def test_format_2_prefixe_plus_sha256(self):
        _, path = self.build(attach_format=2, prefix="ev_")
        nom = os.path.basename(path)
        self.assertTrue(nom.startswith("ev_"))
        self.assertEqual(len(nom), len("ev_") + 64 + len(".csv.gz"))

    def test_format_3_sha256_seul(self):
        _, path = self.build(attach_format=3)
        self.assertEqual(len(os.path.basename(path)), 64 + len(".csv.gz"))

    def test_le_sha256_est_celui_du_CONTENU_produit(self):
        import hashlib
        _, path = self.build(attach_results=2, attach_format=3)
        with open(path, "rb") as f:
            attendu = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(os.path.basename(path), attendu + ".csv")

    def test_un_format_inconnu_a_son_PROPRE_identifiant_de_log(self):
        # ⚠️ This branch used to log id="141", already taken by the
        # results-file trace a hundred lines above -- in BOTH helpers.
        with self.assertRaises(AttachmentError):
            self.build(attach_format=9)
        self.assertIn("146", self.recorder.ids())
        self.assertNotIn("141", [id for niv, id, _ in self.recorder.rows
                                 if niv == "error"])


class WhatGoesWrong(Base):

    def test_un_fichier_de_resultats_illisible_est_nomme_et_non_subi(self):
        # Before: headers stayed None and the failure surfaced as a TypeError
        # inside csv.writerow -- blaming the writer for a read that had already
        # failed and been logged.
        with open(self.results, "wb") as f:
            f.write(b"ceci n'est pas du gzip")
        with self.assertRaises(AttachmentError):
            self.build(attach_results=2)
        self.assertIn("148", self.recorder.ids())

    def test_chaque_appel_a_son_propre_repertoire(self):
        # ⚠️ The system temp dir is shared by every alert action worker; a
        # fixed file name collided between overlapping runs.
        tmp1, _ = self.build()
        tmp2, _ = self.build()
        self.assertNotEqual(tmp1, tmp2)
        self.assertTrue(os.path.isdir(tmp1) and os.path.isdir(tmp2))

    def test_a_failed_build_leaves_no_directory_behind(self):
        # ⚠️ The directory is created before anything can fail, and it is only
        # handed to the caller on success -- so on failure nobody else can
        # remove it. Every failed attachment left one in the shared temp dir
        # of the Splunk host, and the suite left two per run on this machine.
        created = []
        real_mkdtemp = tempfile.mkdtemp

        def recording_mkdtemp(*args, **kwargs):
            path = real_mkdtemp(*args, **kwargs)
            created.append(path)
            return path

        with open(self.results, "wb") as f:
            f.write(b"this is not gzip")
        failures = {
            "unreadable results": dict(attach_results=2),
            "unknown file name format": dict(attach_format=9),
        }
        for label, kwargs in failures.items():
            with self.subTest(failure=label):
                created.clear()
                with unittest.mock.patch.object(
                    attachment_builder.tempfile, "mkdtemp", recording_mkdtemp
                ):
                    with self.assertRaises(AttachmentError):
                        self.build(**kwargs)
                self.assertEqual(len(created), 1)
                self.to_clean.extend(created)
                self.assertFalse(os.path.exists(created[0]))

    def test_le_repertoire_survit_a_l_appel(self):
        # The caller uploads FROM it, then removes it. Cleaning up here would
        # delete the file before it is read.
        tmp, path = self.build()
        self.assertTrue(os.path.isfile(path))
        self.assertTrue(path.startswith(tmp))


class BothCallersShareTheCode(unittest.TestCase):
    """The point of the ticket: one implementation, not two."""

    def test_les_deux_helpers_appellent_le_constructeur_partage(self):
        for nom in ("modalert_thehive_create_a_new_case_helper.py",
                    "modalert_thehive_create_a_new_alert_helper.py"):
            path = os.path.join(BIN, "ta_thehive_cortex", nom)
            with open(path, encoding="utf-8") as f:
                source = f.read()
            with self.subTest(helper=nom):
                self.assertIn("build_attachment(", source)
                # And none of the machinery it replaced is left behind.
                for reste in ("tempfile.mkdtemp", "gzip.open", "hashlib.sha256",
                              "csv.writer", "os.rename"):
                    self.assertNotIn(reste, source)


if __name__ == "__main__":
    unittest.main()
