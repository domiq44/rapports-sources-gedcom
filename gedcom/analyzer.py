"""Analyse les enregistrements GEDCOM et leurs références entre entités."""

from collections import defaultdict
from typing import Dict, List, Tuple, TypedDict

from .utils import GedcomNode, est_reference_gedcom, parcourir

NoteReference = Tuple[GedcomNode, GedcomNode, GedcomNode]
Citation = Tuple[GedcomNode, GedcomNode, List[NoteReference]]


class SourceData(TypedDict):
    """Données d'une source et références résolues vers REPO et NOTE."""

    node: GedcomNode
    deposit_xrefs: List[str]
    note_references: List[NoteReference]


SourcesData = Dict[str, SourceData]


def indexer_entites(racines: List[GedcomNode], tag: str) -> Dict[str, GedcomNode]:
    """Indexe les enregistrements de niveau 0 d'un type par XREF.

    Si un XREF apparaît plusieurs fois, le dernier enregistrement remplace
    le précédent, conformément au comportement conservé par l'analyseur.
    """
    return {
        racine.xref: racine
        for racine in racines
        if racine.level == 0 and racine.tag == tag and racine.xref
    }


def _trouver_depots_associes(
    source: GedcomNode,
    depots_map: Dict[str, GedcomNode],
) -> List[str]:
    """Retourne les XREF REPO définis et référencés par une source."""
    return [
        node.value
        for node in parcourir(source)
        if node.tag == "REPO"
        and est_reference_gedcom(node.value)
        and node.value in depots_map
    ]


def _trouver_notes_associees(
    arbre: GedcomNode,
    notes_map: Dict[str, GedcomNode],
    racine: GedcomNode,
) -> List[NoteReference]:
    """Retourne chaque référence NOTE avec sa racine et son entité résolue."""
    return [
        (node, racine, notes_map[node.value])
        for node in parcourir(arbre)
        if node.tag == "NOTE"
        and est_reference_gedcom(node.value)
        and node.value in notes_map
    ]


def trouver_sources_et_depots(
    racines: List[GedcomNode],
    depots_map: Dict[str, GedcomNode],
) -> SourcesData:
    """Construit les données de source et résout leurs REPO et NOTE.

    Les notes inline restent dans l'arbre de la source. Seules les références
    NOTE dont la cible existe parmi les enregistrements de niveau 0 sont liées.
    """
    sources_data: SourcesData = {}
    notes_map = indexer_entites(racines, "NOTE")

    for racine in racines:
        if racine.level == 0 and racine.tag == "SOUR" and racine.xref:
            sources_data[racine.xref] = {
                "node": racine,
                "deposit_xrefs": _trouver_depots_associes(racine, depots_map),
                "note_references": _trouver_notes_associees(racine, notes_map, racine),
            }

    return sources_data


def trouver_citations(
    racines: List[GedcomNode],
) -> Dict[str, List[Citation]]:
    """Regroupe les références SOUR avec leur racine et les notes liées."""
    citations = defaultdict(list)
    notes_map = indexer_entites(racines, "NOTE")

    for racine in racines:
        for node in parcourir(racine):
            if node.tag == "SOUR" and est_reference_gedcom(node.value):
                citation_xref = node.value
                note_references = _trouver_notes_associees(node, notes_map, racine)
                citations[citation_xref].append((node, racine, note_references))

    return dict(citations)


def regrouper_notes_associees(
    note_references: List[NoteReference],
    citations: List[Citation],
) -> List[NoteReference]:
    """Réunit les références NOTE d'une source et de ses citations, dans l'ordre."""
    return list(note_references) + [
        note_reference
        for _, _, notes_citation in citations
        for note_reference in notes_citation
    ]
