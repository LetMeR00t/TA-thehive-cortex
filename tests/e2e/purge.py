"""Sweep up what a previous run left behind, and report what is still there.

    python -m tests.e2e.purge            # list, change nothing
    python -m tests.e2e.purge --purge    # delete every e2e_ object

⚠️ A recovery that needs a human is not a recovery. A run killed between
creating its saved search and its teardown leaves a scheduled search and an
add-on instance behind; this is what removes them without anyone having to
remember which run it was.

It only ever touches names starting with the campaign prefix. That is the
whole reason every object carries it.
"""

import sys

from . import _config
from ._case import PREFIXE
from ._splunk import ClientSplunk
from ._thehive import ClientTheHive


def _clients():
    splunk = ClientSplunk(
        _config.SPLUNK_MGMT,
        _config.valeur("SPLUNK_USER"),
        _config.valeur("SPLUNK_PASSWORD"),
        _config.APP,
    )
    modele = splunk.lire_instance(_config.valeur("E2E_TEMPLATE_INSTANCE"))
    schema = "https" if str(modele.get("port")) == "443" else "http"
    thehive = ClientTheHive(
        f"{schema}://{modele['host']}:{modele.get('port', '443')}",
        _config.valeur("THEHIVE_USER"),
        _config.valeur("THEHIVE_PASSWORD"),
        modele.get("organisation"),
    )
    return splunk, thehive


def inventaire(splunk, thehive):
    return {
        "saved searches": splunk.recherches_par_prefixe(PREFIXE),
        "instances": splunk.instances_par_prefixe(PREFIXE),
        "accounts": splunk.comptes_par_prefixe(PREFIXE),
        "thehive alerts": [a.get("title") for a in thehive.alertes_par_prefixe_de_titre(PREFIXE)],
        "thehive cases": [c.get("title") for c in thehive.cas_par_prefixe_de_titre(PREFIXE)],
    }


def main(argv):
    raison = _config.raison_du_saut()
    if raison:
        print(raison)
        return 2

    splunk, thehive = _clients()
    restes = inventaire(splunk, thehive)
    total = sum(len(v) for v in restes.values())

    for genre, noms in restes.items():
        print(f"{genre}: {len(noms)}")
        for nom in noms:
            print(f"    {nom}")

    if "--purge" not in argv:
        print("\nnothing was deleted; pass --purge to remove the objects listed above")
        return 0 if total == 0 else 1

    for nom in restes["saved searches"]:
        splunk.supprimer_recherche_sauvegardee(nom)
    for nom in restes["instances"]:
        splunk.supprimer_instance(nom)
    for nom in restes["accounts"]:
        splunk.supprimer_compte(nom)
    efface = thehive.supprimer_par_prefixe(PREFIXE)

    reste = inventaire(splunk, thehive)
    encore = sum(len(v) for v in reste.values())
    print(f"\ndeleted {total - encore} object(s) ({efface} of them in TheHive)")
    if encore:
        # Saying "cleaned" while something is left is exactly the lie this
        # script exists to prevent.
        print(f"⚠️  {encore} object(s) still carry the prefix; see the listing above")
    return 1 if encore else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
