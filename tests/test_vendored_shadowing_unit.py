"""The vendored libraries must win against another add-on's copy.

Splunk add-ons share one interpreter, and this one inserts its `libs` directory
into `sys.path`. If another add-on ships its own `cortex4py` -- which is not
far-fetched, it is a public library -- the two can collide.

⚠️ And the collision has a precise shape that is easy to get wrong. A directory
WITHOUT `__init__.py` is an implicit namespace package (PEP 420), so its
contents merge with any homonymous directory on the path. A directory WITH one
is a regular package and wins immediately, whatever the `sys.path` order.

`cortex4py/` lost its (empty) `__init__.py` in the UCC migration and nobody
noticed for years. Its sub-packages `controllers/` and `models/` kept theirs,
so they were never at risk -- only the ROOT modules were, which is exactly what
`cortex.py` imports: `from cortex4py.api import Api` and
`import cortex4py.exceptions`.

An empty file closes it. A test is what keeps it closed: nothing about a 0-byte
file suggests it matters, and the next cleanup would remove it again.
"""

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIBS = os.path.join(APP_ROOT, 'TA-thehive-cortex', 'package', 'bin',
                    'ta_thehive_cortex', 'libs')


class TestSupplantationDesLibsVendorisees(unittest.TestCase):

    def _autre_add_on(self, racine, module, contenu):
        """Simulate a neighbouring add-on shipping the same package name."""
        paquet = os.path.join(racine, "cortex4py")
        os.makedirs(paquet, exist_ok=True)
        with open(os.path.join(paquet, module), "w", encoding="utf-8") as fh:
            fh.write(contenu)
        return racine

    def _resoudre(self, chemins, module):
        """Where would Python LOAD this module from?

        ⚠️ `find_spec` resolves without EXECUTING. Importing for real would drag
        in `requests`, and the first version of this test failed on that -- while
        the traceback quietly proved the resolution was already correct. Testing
        execution when the question is resolution turns an absent dependency into
        a false alarm about shadowing.

        A separate process because sys.path games do not undo cleanly.
        """
        script = textwrap.dedent(f"""
            import importlib.util
            spec = importlib.util.find_spec({module!r})
            print(spec.origin if spec else "INTROUVABLE")
        """)
        env = dict(os.environ, PYTHONPATH=os.pathsep.join(chemins))
        rendu = subprocess.run([sys.executable, "-c", script],
                               capture_output=True, text=True, env=env)
        return rendu.stdout.strip(), rendu.stderr.strip()

    def test_cortex4py_a_bien_son_init(self):
        """The whole defence is one empty file; assert it exists before the rest.

        Checked separately so a failure says WHICH thing broke: the file being
        gone and the shadowing succeeding are the same symptom otherwise.
        """
        chemin = os.path.join(LIBS, "cortex4py", "__init__.py")
        self.assertTrue(os.path.isfile(chemin),
                        "cortex4py/__init__.py is missing: the package falls back to a "
                        "namespace package and another add-on can shadow its root modules")

    def test_notre_api_gagne_contre_un_homonyme(self):
        with tempfile.TemporaryDirectory() as tmp:
            intrus = self._autre_add_on(
                tmp, "api.py",
                "ORIGINE = 'un autre add-on'\n"
                "class Api:\n"
                "    def __init__(self, *a, **k):\n"
                "        raise RuntimeError('mauvaise implementation')\n",
            )
            # The intruder FIRST on the path: the least favourable order.
            sortie, erreur = self._resoudre([intrus, LIBS], "cortex4py.api")
            self.assertEqual("", erreur, f"import failed: {erreur}")
            self.assertIn(LIBS, sortie,
                          f"cortex4py.api was loaded from the other add-on ({sortie}): "
                          f"the vendored copy was shadowed")

    def test_les_sous_paquets_etaient_deja_proteges(self):
        """Documents WHY the first attempt to demonstrate this failed.

        `controllers/` has its own `__init__.py`, so it is a regular package and
        wins regardless of order. Attacking it proves nothing -- which is what
        made the real hole look absent at first.
        """
        with tempfile.TemporaryDirectory() as tmp:
            paquet = os.path.join(tmp, "cortex4py", "controllers")
            os.makedirs(paquet)
            with open(os.path.join(paquet, "jobs.py"), "w", encoding="utf-8") as fh:
                fh.write("ORIGINE = 'un autre add-on'\n")
            sortie, erreur = self._resoudre([tmp, LIBS], "cortex4py.controllers.jobs")
            self.assertEqual("", erreur, f"import failed: {erreur}")
            self.assertIn(LIBS, sortie)


if __name__ == '__main__':
    unittest.main()
