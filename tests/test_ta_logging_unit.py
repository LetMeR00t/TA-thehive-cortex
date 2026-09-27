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

#: ⚠️ `os.geteuid` does NOT exist on Windows, and a decorator is evaluated at
#: IMPORT time -- writing `os.geteuid() == 0` inline made the whole module fail
#: to load on the PC while staying green on the pod. This suite runs on both.
#: `chmod 000` is also meaningless on Windows: the file stays readable, so the
#: case this test needs simply cannot be built there.
CAN_MAKE_UNREADABLE = hasattr(os, "geteuid") and os.geteuid() != 0

mocks = ['splunk', 'splunk.Intersplunk', 'splunklib', 'splunklib.client']

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _isolation import temporary_mocks  # noqa: E402

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(APP_ROOT, 'TA-thehive-cortex', 'package', 'bin')
if BIN not in sys.path:
    sys.path.insert(0, BIN)

# The REAL module: this file is the one that tests it. If another test
# module leaked a MagicMock for it, we would be asserting on the mock.
with temporary_mocks(mocks):
    import ta_logging  # noqa: E402


class WarningCollector(logging.Handler):
    """Keeps the records rather than the formatted text: we assert on levels."""

    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)

    def at_least_one_warning(self):
        return any(r.levelno >= logging.WARNING for r in self.records)


class TestLevelResolution(unittest.TestCase):

    def setUp(self):
        self._root = tempfile.TemporaryDirectory()
        self.splunk_home = self._root.name
        self.app = os.path.join(self.splunk_home, "etc", "apps", "TA-thehive-cortex")
        os.makedirs(os.path.join(self.app, "local"), exist_ok=True)
        os.makedirs(os.path.join(self.app, "default"), exist_ok=True)
        os.makedirs(os.path.join(self.splunk_home, "var", "log", "splunk"), exist_ok=True)
        self._previous = os.environ.get("SPLUNK_HOME")
        os.environ["SPLUNK_HOME"] = self.splunk_home
        self._counter = 0
        self._loggers = []

    def tearDown(self):
        if self._previous is None:
            os.environ.pop("SPLUNK_HOME", None)
        else:
            os.environ["SPLUNK_HOME"] = self._previous
        # ⚠️ setup_logging() installs a RotatingFileHandler that keeps the log
        # file OPEN. Windows refuses to unlink an open file, so the cleanup
        # below died with WinError 32 while Linux happily removed the tree:
        # the leak was invisible on the CI and fatal on a Windows checkout.
        # Closing here is not tidiness, it is what makes the test isolated.
        for logger in self._loggers:
            for handler in list(logger.handlers):
                logger.removeHandler(handler)
                handler.close()
        self._loggers = []
        self._root.cleanup()

    def _write_settings(self, content, where="local"):
        file_path = os.path.join(self.app, where, "thehive_cortex_settings.conf")
        with open(file_path, "w", encoding="utf-8") as fh:
            fh.write(content)
        return file_path

    def _configure(self):
        """A distinct name per call: loggers are cached by name."""
        self._counter += 1
        name_ = f"level_test_{id(self)}_{self._counter}"
        collector = WarningCollector()
        logging.getLogger("TA-thehive-cortex_" + name_).addHandler(collector)
        logger = ta_logging.setup_logging(name_)
        self._loggers.append(logger)
        return logger, collector

    def test_the_requested_level_is_applied(self):
        self._write_settings("[logging]\nloglevel = DEBUG\n")
        logger, collector = self._configure()
        self.assertEqual(logging.DEBUG, logger.level)
        self.assertFalse(collector.at_least_one_warning(),
                         "a valid configuration must not warn")

    def test_an_unknown_level_is_reported(self):
        self._write_settings("[logging]\nloglevel = VERBOSE\n")
        logger, collector = self._configure()
        self.assertEqual(logging.INFO, logger.level,
                         "the fallback itself is fine")
        self.assertTrue(collector.at_least_one_warning(),
                        "falling back to INFO on an unknown level must be said, "
                        "otherwise the user never learns why DEBUG had no effect")

    @unittest.skipUnless(CAN_MAKE_UNREADABLE,
                         "needs POSIX permissions: chmod 000 does not make a file "
                         "unreadable on Windows, and root reads everything anyway")
    def test_an_unreadable_configuration_is_reported(self):
        # A real file that open() cannot read: this is what reaches the except.
        # A DIRECTORY would not do -- os.path.isfile() returns False for it, so
        # the code takes the ordinary "no local settings" path and must NOT warn.
        file_path = self._write_settings("[logging]\nloglevel = DEBUG\n")
        os.chmod(file_path, 0o000)
        try:
            logger, collector = self._configure()
        finally:
            # Restored here, not via addCleanup: cleanups run AFTER tearDown,
            # which has already removed the temporary tree.
            os.chmod(file_path, 0o600)
        self.assertEqual(logging.INFO, logger.level)
        self.assertTrue(collector.at_least_one_warning(),
                        "an unreadable configuration must leave a trace")


if __name__ == '__main__':
    unittest.main()
