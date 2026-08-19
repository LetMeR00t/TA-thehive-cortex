"""The log level asked for must be the log level obtained -- or say why not.

`setup_logging()` resolves the level from thehive_cortex_settings.conf. Two
distinct paths used to fall back to INFO in complete silence:

1. `except Exception: pass` around the whole resolution -- an unreadable or
   malformed configuration file left no trace at all;
2. `getattr(logging, loglevel.upper(), logging.INFO)` -- a level name Python
   does not know (a typo, or a value from a newer version of the add-on)
   silently became INFO.

Both produce the same symptom: the user sets DEBUG, keeps getting INFO, and
nothing anywhere explains it. A guard that cannot go red is not a guard, and a
fallback that cannot be observed is indistinguishable from a working feature.
"""

import logging
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

mocks = ['splunk', 'splunk.Intersplunk', 'splunklib', 'splunklib.client']
for mod in mocks:
    sys.modules.setdefault(mod, MagicMock())

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(APP_ROOT, 'TA-thehive-cortex', 'package', 'bin')
if BIN not in sys.path:
    sys.path.insert(0, BIN)

import ta_logging  # noqa: E402


class CollecteurDAvertissements(logging.Handler):
    """Keeps the records rather than the formatted text: we assert on levels."""

    def __init__(self):
        super().__init__()
        self.enregistrements = []

    def emit(self, record):
        self.enregistrements.append(record)

    def au_moins_un_avertissement(self):
        return any(r.levelno >= logging.WARNING for r in self.enregistrements)


class TestResolutionDuNiveau(unittest.TestCase):

    def setUp(self):
        self._racine = tempfile.TemporaryDirectory()
        self.splunk_home = self._racine.name
        self.app = os.path.join(self.splunk_home, "etc", "apps", "TA-thehive-cortex")
        os.makedirs(os.path.join(self.app, "local"), exist_ok=True)
        os.makedirs(os.path.join(self.app, "default"), exist_ok=True)
        os.makedirs(os.path.join(self.splunk_home, "var", "log", "splunk"), exist_ok=True)
        self._ancien = os.environ.get("SPLUNK_HOME")
        os.environ["SPLUNK_HOME"] = self.splunk_home
        self._compteur = 0

    def tearDown(self):
        if self._ancien is None:
            os.environ.pop("SPLUNK_HOME", None)
        else:
            os.environ["SPLUNK_HOME"] = self._ancien
        self._racine.cleanup()

    def _ecrire_reglages(self, contenu, ou="local"):
        chemin = os.path.join(self.app, ou, "thehive_cortex_settings.conf")
        with open(chemin, "w", encoding="utf-8") as fh:
            fh.write(contenu)
        return chemin

    def _configurer(self):
        """A distinct name per call: loggers are cached by name."""
        self._compteur += 1
        nom = f"essai_niveau_{id(self)}_{self._compteur}"
        collecteur = CollecteurDAvertissements()
        logging.getLogger("TA-thehive-cortex_" + nom).addHandler(collecteur)
        return ta_logging.setup_logging(nom), collecteur

    def test_le_niveau_demande_est_applique(self):
        self._ecrire_reglages("[logging]\nloglevel = DEBUG\n")
        logger, collecteur = self._configurer()
        self.assertEqual(logging.DEBUG, logger.level)
        self.assertFalse(collecteur.au_moins_un_avertissement(),
                         "a valid configuration must not warn")

    def test_un_niveau_inconnu_est_signale(self):
        self._ecrire_reglages("[logging]\nloglevel = VERBOSE\n")
        logger, collecteur = self._configurer()
        self.assertEqual(logging.INFO, logger.level,
                         "the fallback itself is fine")
        self.assertTrue(collecteur.au_moins_un_avertissement(),
                        "falling back to INFO on an unknown level must be said, "
                        "otherwise the user never learns why DEBUG had no effect")

    def test_une_configuration_illisible_est_signalee(self):
        # A directory where a file is expected: open() raises IsADirectoryError.
        chemin = os.path.join(self.app, "local", "thehive_cortex_settings.conf")
        os.makedirs(chemin, exist_ok=True)
        logger, collecteur = self._configurer()
        self.assertEqual(logging.INFO, logger.level)
        self.assertTrue(collecteur.au_moins_un_avertissement(),
                        "an unreadable configuration must leave a trace")


if __name__ == '__main__':
    unittest.main()
