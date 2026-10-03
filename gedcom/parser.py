"""Lecture et construction des arbres syntaxiques GEDCOM."""

import sys
from pathlib import Path
from typing import Dict, List

from .utils import GEDCOM_LINE_RE, GedcomNode


def lire_fichier(path: Path, encodage: str = "auto") -> List[str]:
    """Lit un fichier GEDCOM avec l'encodage demandé ou une détection simple."""
    donnees = path.read_bytes()

    if encodage != "auto":
        try:
            return donnees.decode(encodage).splitlines()
        except UnicodeDecodeError as e:
            raise UnicodeDecodeError(f"Erreur de décodage avec {encodage}", e.object, e.start, e.end, str(e))

    encodages = [
        "utf-8-sig",
        "utf-8",
        "cp1252",
        "iso-8859-1",
    ]

    for nom_encodage in encodages:
        try:
            return donnees.decode(nom_encodage).splitlines()
        except UnicodeDecodeError:
            continue

    raise UnicodeDecodeError(
        "unknown",
        donnees,
        0,
        len(donnees),
        "Encodage du fichier impossible à déterminer",
    )

def analyser_lignes(lines: List[str]) -> List[GedcomNode]:
    """Construit les arbres GEDCOM et retourne leurs nœuds de niveau 0.

    Les lignes invalides et sauts de niveau sont signalés sur stderr puis
    ignorés; les XREF dupliqués sont signalés sans interrompre l'analyse.
    """
    racines: List[GedcomNode] = []
    pile: List[GedcomNode] = []
    premiere_ligne_par_xref: Dict[str, int] = {}

    for numero, raw_line in enumerate(lines, start=1):
        ligne = raw_line.rstrip("\r\n")

        if not ligne.strip():
            continue

        match = GEDCOM_LINE_RE.match(ligne)

        if not match:
            print(
                f"Avertissement : ligne GEDCOM ignorée "
                f"({numero}) : {ligne}",
                file=sys.stderr,
            )
            continue

        level = int(match.group(1))
        xref = match.group(2)
        tag = match.group(3)
        value = match.group(4) or ""

        if level == 0 and xref:
            if xref in premiere_ligne_par_xref:
                print(
                    f"Avertissement : XREF dupliqué {xref} aux lignes "
                    f"{premiere_ligne_par_xref[xref]} et {numero}.",
                    file=sys.stderr,
                )
            else:
                premiere_ligne_par_xref[xref] = numero

        node = GedcomNode(
            level=level,
            xref=xref,
            tag=tag,
            value=value,
            raw_line=ligne,
        )

        if level == 0:
            racines.append(node)
            pile = [node]
            continue

        while pile and pile[-1].level >= level:
            pile.pop()

        if not pile:
            print(
                f"Avertissement : hiérarchie invalide à la ligne "
                f"{numero} : {ligne}",
                file=sys.stderr,
            )
            racines.append(node)
            pile = [node]
            continue

        if level > pile[-1].level + 1:
            print(
                f"Avertissement : saut de niveau invalide à la ligne "
                f"{numero} : {ligne}",
                file=sys.stderr,
            )
            continue

        pile[-1].add_child(node)
        pile.append(node)

    return racines


def construire_xref_map(racines: List[GedcomNode]) -> Dict[str, GedcomNode]:
    """Compatibilité : délègue l'indexation REPO à l'analyseur métier."""
    from .analyzer import indexer_entites

    return indexer_entites(racines, "REPO")
