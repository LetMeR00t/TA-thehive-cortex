"""Gitea #45: the Cortex job form must post Cortex's own TLP/PAP scale.

`cortex_run_a_new_job.html` offered WHITE=1 ... RED=4 while Cortex, the
`cortexrun` command and `cortex.colorCode` all count WHITE=0 ... RED=3. The
value is forwarded untouched, so every label was one step too high: the
shipped default `3`, displayed as AMBER, created RED jobs, and RED (4) was off
the scale. The TheHive forms are not concerned: TheHive's TLP has a fifth
level (AMBER+STRICT) and their values already match TheHive.

The form, the `.conf` default and `colorCode` are three statements of one
scale; this pins them together from the sources, without importing Splunk.
"""

import ast
import configparser
import os
import re
import unittest

PACKAGE = os.path.join(os.path.dirname(__file__), "..", "TA-thehive-cortex", "package")
FORM = os.path.join(PACKAGE, "default", "data", "ui", "alerts", "cortex_run_a_new_job.html")
CONF = os.path.join(PACKAGE, "default", "alert_actions.conf")
CORTEX = os.path.join(PACKAGE, "bin", "cortex.py")


def _color_code():
    tree = ast.parse(open(CORTEX, encoding="utf-8").read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "colorCode" for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError("colorCode not found in cortex.py")


def _form_options(param):
    html = open(FORM, encoding="utf-8").read()
    select = re.search(
        r'<select[^>]*name="action\.cortex_run_a_new_job\.param\.%s"[^>]*>(.*?)</select>' % param,
        html,
        re.S,
    )
    assert select, "no <select> for param.%s" % param
    return {
        label.strip(): int(value)
        for value, label in re.findall(r'<option value="(\d+)"[^>]*>([^<]+)</option>', select.group(1))
    }


class CortexTlpPapScale(unittest.TestCase):
    def setUp(self):
        self.scale = _color_code()
        conf = configparser.ConfigParser(interpolation=None, strict=False)
        conf.read(CONF, encoding="utf-8")
        self.action = conf["cortex_run_a_new_job"]

    def test_form_posts_cortex_scale(self):
        for param in ("tlp", "pap"):
            with self.subTest(param=param):
                self.assertEqual(_form_options(param), self.scale)

    def test_default_is_amber(self):
        for param in ("tlp", "pap"):
            with self.subTest(param=param):
                self.assertEqual(int(self.action["param.%s" % param]), self.scale["AMBER"])


if __name__ == "__main__":
    unittest.main()
