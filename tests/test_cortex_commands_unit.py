"""Cortex commands: two defects that make them fail on the very first call.

Both are invisible to every existing test because nothing ever exercises these
code paths offline. They are not edge cases -- they are the nominal path.

1. `cortex_refresh_analyzers.py` calls `initialize_cortex_instance()` without
   the mandatory positional `acronym`, so the command raises TypeError and has
   never been able to run. This is why it is the only command missing from both
   `docs/commands.md` and `searchbnf.conf`: it was never documented because it
   was never used.

2. `Cortex.addJob()` reads `self.logger` while `Cortex.__init__` only ever sets
   `self.logger_file`, so `cortexrun` raises AttributeError. The mirror defect
   lives in `CortexJob.__init__`, which sets `self.logger` and then reads
   `self.logger_file` on its error branch.

The first test walks EVERY call site rather than the one known to be broken:
a signature mismatch is a class of defect, and pinning a single caller would
let the next one through.
"""

import ast
import inspect
import os
import sys
import unittest
from unittest.mock import MagicMock

# Mock EVERYTHING that is not available locally
mocks = [
    'splunklib', 'splunklib.client', 'solnlib', 'solnlib.log',
    'solnlib.modular_input', 'solnlib.utils', 'ta_thehive_cortex_declare',
    'certifi', 'common', 'ta_logging', 'requests', 'requests.adapters',
    'requests.auth', 'urllib3', 'splunk', 'splunk.Intersplunk', 'globals',
]

for mod in mocks:
    sys.modules.setdefault(mod, MagicMock())

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(APP_ROOT, 'TA-thehive-cortex', 'package', 'bin')
for p in (BIN,
          os.path.join(BIN, 'ta_thehive_cortex'),
          os.path.join(BIN, 'ta_thehive_cortex', 'libs')):
    if p not in sys.path:
        sys.path.insert(0, p)

import cortex as cortex_module  # noqa: E402


class TestInitializeCortexInstanceCallSites(unittest.TestCase):
    """Every caller must bind against the real signature.

    Reading the source rather than importing it is deliberate: these modules
    are Splunk scripts that execute work at import time.
    """

    #: Arguments we can substitute for any expression, since only ARITY and
    #: keyword NAMES decide whether the call binds.
    JETON = object()

    def _call_sites(self):
        signature = inspect.signature(cortex_module.initialize_cortex_instance)
        for nom in sorted(os.listdir(BIN)):
            if not nom.endswith('.py'):
                continue
            chemin = os.path.join(BIN, nom)
            with open(chemin, encoding='utf-8') as fh:
                arbre = ast.parse(fh.read(), filename=nom)
            for noeud in ast.walk(arbre):
                if not isinstance(noeud, ast.Call):
                    continue
                cible = noeud.func
                if isinstance(cible, ast.Name) and cible.id == 'initialize_cortex_instance':
                    yield nom, noeud, signature

    def test_every_call_binds(self):
        trouves = 0
        fautifs = []
        for nom, noeud, signature in self._call_sites():
            trouves += 1
            positionnels = [self.JETON] * len(noeud.args)
            nommes = {kw.arg: self.JETON for kw in noeud.keywords if kw.arg}
            try:
                signature.bind(*positionnels, **nommes)
            except TypeError as err:
                fautifs.append(f"{nom}:{noeud.lineno} -> {err}")

        self.assertGreater(trouves, 0, "no call site found -- the test is blind")
        self.assertEqual(
            [], fautifs,
            "call sites that do not match initialize_cortex_instance():\n  "
            + "\n  ".join(fautifs),
        )


class TestCortexAddJobAttributes(unittest.TestCase):
    """`addJob` must only read attributes that `__init__` actually sets."""

    def _cortex_sans_reseau(self):
        """A Cortex whose __init__ is bypassed: it performs a live API call."""
        instance = object.__new__(cortex_module.Cortex)
        instance.logger_file = MagicMock()
        instance.analyzers = MagicMock()
        instance.analyzers.get_by_type.return_value = [MagicMock(id="a1", name="an")]
        instance._Cortex__jobs = []
        instance._Cortex__sid = "sid"
        return instance

    def test_addjob_does_not_read_an_undefined_attribute(self):
        instance = self._cortex_sans_reseau()
        # A dataType from the hardcoded list, so the type gate is not what fails.
        instance.addJob(data="1.2.3.4", dataType="ip")
        self.assertEqual(1, len(instance.getJobs()))

    def test_addjob_accepts_a_datatype_outside_the_frozen_list(self):
        """Cortex is the authority on its own dataTypes, not a frozen copy.

        `hostname` and `autonomous-system` are absent from cortex.py's list
        while being present in the one carried by modalert_thehive_common.py --
        the two copies disagree, and the stricter one used to call sys.exit().
        """
        instance = self._cortex_sans_reseau()
        instance.addJob(data="a-host", dataType="hostname")
        self.assertEqual(1, len(instance.getJobs()))


if __name__ == '__main__':
    unittest.main()
