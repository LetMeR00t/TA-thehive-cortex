#!/usr/bin/env python3
"""A panel nobody can ever see, and a comment that breaks the file.

Two failures this repository shipped, both invisible to a reading:

**1. A panel gated on a token nothing sets.** `thehive_statistics.xml` hid two
panels behind `depends="$always_hidden$"`. A hidden panel does not dispatch its
search — and those two searches were the only producers of the tokens the main
chart consumed. The chart therefore waited for input forever, with no error and
no empty-result message. The view was dead for four releases.

**2. A panel invisible for its input's DEFAULT value.** `thehive_alerts.xml`
gated its results panel on a token set by `<condition value="list">`, while the
input's own `<default>` is already `list`. A `<change>` does not fire for the
value an input already has at load, so the panel was absent on arrival and
appeared only after the user moved the input away and back. Its twin
`cases.xml` has no such gate — two files 86 % identical behaving in opposite
ways.

⚠️ Note how narrow that rule is. A token set inside a `<change>` is normal and
usually deliberate: a panel that appears once you pick "CREATE" is the point.
Reporting all of them would be a guard crying wolf, and a guard that cries wolf
gets switched off. Only the mismatch with the DEFAULT value is a defect.

**3. A double dash inside an XML comment.** Illegal, and it makes the whole
view unparseable. Caught twice while writing the fixes above, which is exactly
why it is checked here rather than remembered.

    python tools/checks/views_are_reachable.py

Exit 0 when every view parses and every gated panel can actually appear.
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
UI = RACINE / "TA-thehive-cortex" / "package" / "default" / "data" / "ui"

#: Jetons que Splunk fournit lui-même, jamais posés par la vue.
FOURNIS_PAR_SPLUNK = re.compile(
    r"^(?:env:|job\.|result\.|click\.|row\.|earliest|latest|form\.)"
)

#: L'idiome « panneau porteur de CSS », délibérément invisible.
IDIOMES_INVISIBLES = {"alwaysHideCSSPanel"}


def vues():
    for chemin in sorted(UI.rglob("*.xml")):
        yield chemin


def jetons_poses(texte: str) -> set[str]:
    poses = set()
    poses.update(re.findall(r'<set\s+token="([^"]+)"', texte))
    poses.update(re.findall(r'<eval\s+token="([^"]+)"', texte))
    poses.update(re.findall(r'<input[^>]*\stoken="([^"]+)"', texte))
    poses.update(re.findall(r'<unset\s+token="([^"]+)"', texte))
    return poses


def jetons_absents_au_chargement(texte: str) -> set[str]:
    """Les jetons qu'aucune valeur PAR DÉFAUT ne produit.

    Pour chaque input : sa valeur par défaut, puis les jetons que son `<change>`
    pose pour cette valeur-là. Un jeton posé uniquement pour une AUTRE valeur
    est absent au chargement, et le panneau qui en dépend avec lui.
    """
    absents = set()
    for bloc in re.findall(r"<input\b.*?</input>", texte, re.S):
        defaut = re.search(r"<default>(.*?)</default>", bloc, re.S)
        if not defaut:
            continue
        valeur_defaut = defaut.group(1).strip()
        for condition in re.findall(r"<condition\b([^>]*)>(.*?)</condition>",
                                    bloc, re.S):
            attributs, corps = condition
            vise = re.search(r'value="([^"]*)"', attributs)
            if not vise:
                continue
            # ⚠️ SEUL ce cas est un défaut : la condition vise la valeur que
            # l'input porte DÉJÀ, donc le panneau devrait être là à l'arrivée
            # — et il n'y est pas, parce qu'un <change> ne se déclenche pas au
            # chargement.
            #
            # Une condition qui vise une AUTRE valeur cache le panneau
            # volontairement : c'est tout l'intérêt d'un formulaire à modes.
            # Le signaler serait crier au loup, et un garde qui crie au loup
            # finit débranché.
            if vise.group(1) == valeur_defaut:
                absents |= set(re.findall(r'<set\s+token="([^"]+)"', corps))
    hors_change = jetons_poses(re.sub(r"<change>.*?</change>", "", texte, flags=re.S))
    return absents - hors_change


def main() -> int:
    if not UI.is_dir():
        print(f"views not found: {UI}", file=sys.stderr)
        return 1

    constats = []
    avertissements = []

    for chemin in vues():
        relatif = chemin.relative_to(RACINE)
        brut = chemin.read_text(encoding="utf-8")
        # ⚠️ Retirer les commentaires AVANT de chercher un motif : sinon le
        # garde se dénonce sur la phrase qui explique le défaut qu'il corrige.
        texte = re.sub(r"<!--.*?-->", "", brut, flags=re.S)

        # --- 3. un `--` dans un commentaire rend le fichier illisible --------
        for corps in re.findall(r"<!--(.*?)-->", brut, re.S):
            if "--" in corps:
                constats.append(
                    f"{relatif}: a comment contains a double dash, which is "
                    f"illegal in XML and makes the whole view unparseable"
                )

        try:
            ET.parse(chemin)
        except ET.ParseError as e:
            constats.append(f"{relatif}: does not parse — {e}")
            continue

        poses = jetons_poses(texte)
        absents_au_chargement = jetons_absents_au_chargement(texte)

        for attribut in ("depends", "rejects"):
            for expression in re.findall(rf'{attribut}="([^"]+)"', texte):
                for jeton in re.findall(r"\$([^$,]+)\$", expression):
                    if jeton in IDIOMES_INVISIBLES or FOURNIS_PAR_SPLUNK.match(jeton):
                        continue
                    if jeton not in poses:
                        constats.append(
                            f"{relatif}: a panel is gated on ${jeton}$, which "
                            f"nothing in this view ever sets. It can never "
                            f"appear, and its searches never run"
                        )
                    elif attribut == "depends" and jeton in absents_au_chargement:
                        avertissements.append(
                            f"{relatif}: a panel is gated on ${jeton}$, set by "
                            f"a <condition> matching an input's DEFAULT value. "
                            f"A <change> does not fire at load, so the panel is "
                            f"absent on arrival until the user moves that input "
                            f"away and back"
                        )

    for a in avertissements:
        print(f"  ⚠️  {a}")
    for c in constats:
        print(f"  {c}")

    if constats:
        print()
        print("A panel that cannot appear does not report an error: it is simply")
        print("not there, and its searches never run.")
        return 1

    print(f"every view parses; every gated panel can appear"
          + (f" ({len(avertissements)} reported)" if avertissements else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
