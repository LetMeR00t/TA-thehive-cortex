"""Which stored value becomes the password an account authenticates with.

This rule arbitrates **secrets**, it is genuinely subtle, and until now it was
at **0 % coverage** while existing in two places: inline in
`Instances.__init__` and copied verbatim into a manual diagnostic script. The
only thing resembling a test queried a real Splunk, collected nothing (a bare
module-level function, no `TestCase`) and asserted nothing at all -- while
printing the first characters of a real API key to stdout.

⚠️ Every value below is fabricated. A test that needs a real credential to be
meaningful is a test that leaks one.
"""

import os
import sys
import unittest
from collections import namedtuple
from unittest.mock import MagicMock

mocks = [
    'splunklib', 'splunklib.client', 'solnlib', 'solnlib.log',
    'solnlib.modular_input', 'solnlib.utils', 'ta_thehive_cortex_declare',
    'splunk', 'splunk.Intersplunk', 'splunk.rest', 'globals', 'certifi',
    'requests', 'requests.adapters', 'requests.auth', 'requests.exceptions',
    'urllib3', 'urllib3.util', 'urllib3.util.retry', 'tomark',
]

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _isolation import mocks_temporaires  # noqa: E402

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(APP_ROOT, 'TA-thehive-cortex', 'package', 'bin')
for p in (BIN,
          os.path.join(BIN, 'ta_thehive_cortex'),
          os.path.join(BIN, 'ta_thehive_cortex', 'libs')):
    if p not in sys.path:
        sys.path.insert(0, p)

with mocks_temporaires(mocks):
    import common

SEP = common.CRED_SEP
REALM = "__REST_CREDENTIAL__#TA-thehive-cortex#configs/conf-thehive_cortex_accounts"

# storage_passwords entries are objects; the function only ever reads three
# attributes, so a namedtuple is a FAITHFUL substitute -- not a mock that
# answers to any name it is asked for.
Entry = namedtuple("Entry", "realm username clear_password")


def entry(account, value, realm=REALM, champ="api_key"):
    return Entry(realm, f"{account}{SEP}{champ}", value)


class UccUsernameSplitting(unittest.TestCase):

    def test_le_separateur_ucc_est_retire(self):
        self.assertEqual(
            common.account_from_ucc_username(f"local{SEP}api_key"), "local")

    def test_un_nom_sans_separateur_est_rendu_tel_quel(self):
        self.assertEqual(common.account_from_ucc_username("local"), "local")


class PasswordSelection(unittest.TestCase):

    def test_une_seule_entree_brute(self):
        passwords, discarded = common.pick_password([entry("local", "abcdef")])
        self.assertEqual(passwords, {"local": "abcdef"})
        self.assertEqual(discarded, [])

    def test_un_objet_json_est_deballe(self):
        passwords, _ = common.pick_password([entry("local", '{"password": "abcdef"}')])
        self.assertEqual(passwords, {"local": "abcdef"})

    def test_un_json_sans_membre_password_garde_le_texte_brut(self):
        # `.get("password", raw)` returns the raw text, which equals `raw`,
        # so the entry is NOT considered JSON-sourced. That equality is the
        # whole marker of provenance.
        raw = '{"username": "alice"}'
        passwords, _ = common.pick_password([entry("local", raw)])
        self.assertEqual(passwords, {"local": raw})

    def test_un_json_qui_n_est_pas_un_objet_reste_brut(self):
        passwords, _ = common.pick_password([entry("local", '["abcdef"]')])
        self.assertEqual(passwords, {"local": '["abcdef"]'})

    def test_un_texte_non_json_ne_leve_rien(self):
        passwords, _ = common.pick_password([entry("local", "pas du json")])
        self.assertEqual(passwords, {"local": "pas du json"})

    def test_un_realm_etranger_est_ignore(self):
        passwords, _ = common.pick_password(
            [entry("local", "abcdef", realm="__REST_CREDENTIAL__#autre-app#x")])
        self.assertEqual(passwords, {})

    def test_un_realm_vide_est_ignore(self):
        passwords, _ = common.pick_password([entry("local", "abcdef", realm="")])
        self.assertEqual(passwords, {})

    def test_un_realm_absent_est_ignore(self):
        passwords, _ = common.pick_password([Entry(None, "local", "abcdef")])
        self.assertEqual(passwords, {})

    def test_les_valeurs_masquees_sont_ignorees(self):
        for mask in common.MASQUES:
            with self.subTest(mask=mask):
                passwords, discarded = common.pick_password([entry("local", mask)])
                self.assertEqual(passwords, {})
                # A mask is not garbage: Splunk simply refused to show it.
                self.assertEqual(discarded, [])

    def test_une_valeur_contenant_le_separateur_est_du_rebut(self):
        passwords, discarded = common.pick_password([entry("local", f"aa{SEP}bb")])
        self.assertEqual(passwords, {})
        self.assertEqual(discarded, ["local"])

    def test_un_nom_de_compte_sans_separateur_fonctionne(self):
        passwords, _ = common.pick_password([Entry(REALM, "local", "abcdef")])
        self.assertEqual(passwords, {"local": "abcdef"})


class Arbitration(unittest.TestCase):
    """Two entries for the same account. Which one wins, and why."""

    def test_le_json_bat_le_brut_meme_plus_court(self):
        passwords, _ = common.pick_password([
            entry("local", "une-tres-longue-value-brute"),
            entry("local", '{"password": "court"}', champ="password"),
        ])
        self.assertEqual(passwords, {"local": "court"})

    def test_le_json_gagne_aussi_quand_il_arrive_en_premier(self):
        # ⚠️ Order matters in a fold. A rule that only holds in one direction
        # is a rule that depends on how Splunk happens to enumerate.
        passwords, _ = common.pick_password([
            entry("local", '{"password": "court"}', champ="password"),
            entry("local", "une-tres-longue-value-brute"),
        ])
        self.assertEqual(passwords, {"local": "court"})

    def test_a_provenance_egale_la_plus_longue_gagne(self):
        passwords, _ = common.pick_password([
            entry("local", "court"),
            entry("local", "beaucoup-plus-longue"),
        ])
        self.assertEqual(passwords, {"local": "beaucoup-plus-longue"})

    def test_a_provenance_egale_la_plus_courte_ne_supplante_pas(self):
        passwords, _ = common.pick_password([
            entry("local", "beaucoup-plus-longue"),
            entry("local", "court"),
        ])
        self.assertEqual(passwords, {"local": "beaucoup-plus-longue"})

    def test_deux_json_a_longueur_egale_le_premier_reste(self):
        passwords, _ = common.pick_password([
            entry("local", '{"password": "aaaaaa"}'),
            entry("local", '{"password": "bbbbbb"}'),
        ])
        self.assertEqual(passwords, {"local": "aaaaaa"})

    def test_les_comptes_sont_arbitres_separement(self):
        passwords, _ = common.pick_password([
            entry("local", "aaaa"),
            entry("distant", '{"password": "bb"}'),
            entry("local", "aaaaaaaa"),
        ])
        self.assertEqual(passwords, {"local": "aaaaaaaa", "distant": "bb"})


class AMalformedEntryCostsOnlyItself(unittest.TestCase):
    """⚠️ The defect this extraction fixes, and the reason it is worth naming.

    A JSON payload can carry a non-string `password`. The garbage test then ran
    `SEP in value` on an int and raised TypeError -- inside the caller's
    blanket `try/except`, which abandoned the whole loop. One malformed entry
    cost the passwords of **every other account**, and the only trace was a
    single S3_ERROR line mentioning an unrelated-looking type error.
    """

    def test_un_mot_de_passe_non_textuel_est_ecarte_seul(self):
        passwords, discarded = common.pick_password([
            entry("local", '{"password": 1234}'),
            entry("distant", "abcdef"),
        ])
        self.assertEqual(passwords, {"distant": "abcdef"})
        self.assertEqual(discarded, ["local"])

    def test_un_password_objet_est_ecarte_seul(self):
        passwords, discarded = common.pick_password([
            entry("local", '{"password": {"k": "v"}}'),
            entry("distant", "abcdef"),
        ])
        self.assertEqual(passwords, {"distant": "abcdef"})
        self.assertEqual(discarded, ["local"])


class TheFunctionLogsNothing(unittest.TestCase):
    """A value that must never reach a log file is never handed to a logger."""

    def test_aucune_dependance_a_un_logger(self):
        # The signature takes no logger, and the module's own logger is not
        # touched: the caller decides what to say about the accounts named in
        # `discarded` -- account NAMES, never values.
        import inspect
        parameters = inspect.signature(common.pick_password).parameters
        self.assertEqual(list(parameters), ["entries", "app_name"])


if __name__ == "__main__":
    unittest.main()
