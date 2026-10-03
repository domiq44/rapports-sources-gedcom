"""Rendu des rapports GEDCOM dans le terminal."""

import sys
from typing import IO, Dict, List, Optional, Tuple

from .analyzer import Citation, SourcesData, regrouper_notes_associees
from .utils import GedcomNode, ancetre_evenement, cle_numerique_xref, est_reference_gedcom

# =================================================================
# --- Constantes ANSI (Pour le mode Console) ---
# =================================================================
RESET = "\033[0m"
GRIS = "\033[90m"
CYAN = "\033[96m"
VERT = "\033[92m"
JAUNE = "\033[93m"
MAGENTA = "\033[95m"
BLANC = "\033[97m"


# =================================================================
# --- FONCTIONS D'AFFICHAGE (Console) ---
# =================================================================

def formater_ligne_gedcom(
    node: GedcomNode,
    indentation: str,
    colorise: bool,
) -> str:
    """Colorise une ligne GEDCOM tout en reconstruisant une indentation lisible."""
    if not colorise:
        return f"{indentation}{node.raw_line}"

    niveau = f"{GRIS}{node.level}{RESET}"
    xref = ""
    if node.xref:
        xref = f"{CYAN}{node.xref}{RESET} "
    tag = f"{JAUNE}{node.tag}{RESET}"
    valeur = ""
    if node.value:
        if est_reference_gedcom(node.value):
            valeur = f" {VERT}{node.value}{RESET}"
        else:
            valeur = f" {BLANC}{node.value}{RESET}"
    
    if node.tag == "REPO" and node.value:
        valeur = f" {MAGENTA}{node.value}{RESET}"

    return f"{indentation}{niveau} {xref}{tag}{valeur}"


def afficher_arbre(
    node: GedcomNode,
    colorise: bool,
    indentation_level: int,
    output_stream: IO[str]
) -> None:
    """Affiche un nœud et tous ses descendants en respectant l'indentation de base."""

    if indentation_level < 0:
        indentation = ""
    else:
        profondeur = node.level - indentation_level
        indentation = "  " * max(profondeur, 0)

    line_to_write = formater_ligne_gedcom(node, indentation, colorise)
    output_stream.write(line_to_write + "\n")

    for enfant in node.children:
        afficher_arbre(enfant, colorise=colorise, indentation_level=indentation_level, output_stream=output_stream)


def _afficher_notes_associees(
    note_references: List[Tuple[GedcomNode, GedcomNode, GedcomNode]],
    colorise: bool,
    indentation_level: int,
    output_stream: IO[str],
    cible: str = "cette source",
) -> None:
    """Rend les occurrences NOTE et leurs entités complètes associées."""
    if not note_references:
        output_stream.write(f"\n{'-' * 80}\nAucune note trouvée pointant vers {cible}.\n")
        return

    output_stream.write(f"\n\n{'-' * 80}\n{'=' * 20} NOTES RÉFÉRENCÉES ({len(note_references)}) {'=' * 20}\n")
    for numero_note, (note_reference, racine, note_node) in enumerate(note_references, start=1):
        contexte = ancetre_evenement(note_reference, racine)
        output_stream.write(f"\n--- NOTE {numero_note}/{len(note_references)} ---\n")
        output_stream.write(f"Contexte d'apparition: {contexte}\n")
        afficher_arbre(note_node, colorise=colorise, indentation_level=indentation_level, output_stream=output_stream)
# =================================================================
# --- FONCTIONS DÉLÉGUÉES (Logique métier pour chaque mode) ---
# =================================================================

def _lister_sources(
    sources_data: SourcesData,
    colorise: bool,
    indentation_level: int,
    output_stream: IO[str]
) -> None:
    """Liste les sources, leur arbre et les notes référencées."""
    total_sources = len(sources_data)
    output_stream.write(f"\n{'=' * 20} LISTING DES SOURCES (SOUR) UNIQUEMENT ({total_sources}) {'=' * 20}\n")

    if not sources_data:
        output_stream.write("[INFO] Aucune source 0 SOUR trouvée.\n")
        return

    identifiants_tries = sorted(sources_data.keys(), key=cle_numerique_xref)
    
    for numero_source, identifiant in enumerate(identifiants_tries, start=1):
        data = sources_data[identifiant]
        source = data["node"]
        
        output_stream.write(f"\n--- SOURCE {numero_source}/{total_sources} : {identifiant} ---\n")
        afficher_arbre(source, colorise=colorise, indentation_level=indentation_level, output_stream=output_stream)
        _afficher_notes_associees(data["note_references"], colorise, indentation_level, output_stream)


def _lister_depots(
    xref_map: Dict[str, GedcomNode],
    colorise: bool,
    indentation_level: int,
    output_stream: IO[str]
) -> None:
    """Logique pour le mode 'depots' (CLI)."""
    output_stream.write(f"\n{'=' * 20} LISTING DES DÉPÔTS ({len(xref_map)}) {'=' * 20}\n")

    if not xref_map:
        output_stream.write("[INFO] Aucun dépôt (REPO) trouvé dans le fichier.\n")
        return

    all_repo_xrefs = sorted(xref_map.keys(), key=cle_numerique_xref)
    
    for xref in all_repo_xrefs:
        repo_node = xref_map[xref]
        
        output_stream.write(f"\n--- DÉPOT : {xref} ---\n")
        afficher_arbre(repo_node, colorise=colorise, indentation_level=indentation_level, output_stream=output_stream)


def _lister_citations(
    citations: Dict[str, List[Citation]],
    sources_data: SourcesData,
    colorise: bool,
    indentation_level: int,
    output_stream: IO[str]
) -> None:
    """Logique pour le mode 'citations' (CLI)."""
    output_stream.write(f"\n{'=' * 20} LISTING DES CITATIONS {'=' * 20}\n")
    
    citations_connues = {
        identifiant: liste
        for identifiant, liste in citations.items()
        if identifiant in sources_data
    }
    
    citations_inconnues = {
        identifiant: liste
        for identifiant, liste in citations.items()
        if identifiant not in sources_data
    }
    
    total_citations_connues = sum(len(v) for v in citations_connues.values())
    total_citations_inconnues = sum(len(v) for v in citations_inconnues.values())

    # Affichage des citations CONNUES
    if total_citations_connues > 0:
        output_stream.write(f"\n{'=' * 10} CITATIONS CONNUES ({total_citations_connues}) {'=' * 10}\n")
        identifiants_tries_connus = sorted(citations_connues.keys(), key=cle_numerique_xref)

        for identifiant in identifiants_tries_connus:
            liste_citations = citations_connues[identifiant]
            note_references_groupe = regrouper_notes_associees(
                sources_data[identifiant]["note_references"], liste_citations
            )
            output_stream.write(f"\n--- CITATIONS POINTANT VERS SOURCE {identifiant} ({len(liste_citations)}) ---\n")
            
            for numero_citation, (citation, racine, note_references) in enumerate(liste_citations, start=1):
                contexte = ancetre_evenement(citation, racine)
                output_stream.write(f"\n[CITE {numero_citation}/{len(liste_citations)}] Contexte d'apparition: {contexte}\n")
                afficher_arbre(citation, colorise=colorise, indentation_level=indentation_level, output_stream=output_stream)
            _afficher_notes_associees(note_references_groupe, colorise, indentation_level, output_stream, "cette source et ses citations")
    else:
        output_stream.write("\n[INFO] Aucune citation trouvée pointant vers une source SOUR définie.\n")

    # Affichage des citations INCONNUES
    if total_citations_inconnues > 0:
        output_stream.write(f"\n{'=' * 10} CITATIONS INCONNUES ({total_citations_inconnues}) {'=' * 10}\n")

        identifiants_inconnus_tries = sorted(citations_inconnues.keys(), key=cle_numerique_xref)

        for identifiant in identifiants_inconnus_tries:
            liste = citations_inconnues[identifiant]
            note_references_groupe = regrouper_notes_associees([], liste)
            output_stream.write(f"\n--- CITATIONS POINTANT VERS XREF INCONNU {identifiant} ({len(liste)}) ---\n")
            
            for numero_citation, (citation, racine, note_references) in enumerate(liste, start=1):
                contexte = ancetre_evenement(citation, racine)
                output_stream.write(f"\n[CITE {numero_citation}/{len(liste)}] Contexte d'apparition: {contexte}\n")
                afficher_arbre(citation, colorise=colorise, indentation_level=indentation_level, output_stream=output_stream)
            _afficher_notes_associees(note_references_groupe, colorise, indentation_level, output_stream, "ces citations")
    else:
        output_stream.write("\n[INFO] Aucune citation trouvée pointant vers un XREF non défini comme source.\n")


def _lister_sources_et_depots(
    sources_data: SourcesData,
    xref_map: Dict[str, GedcomNode],
    colorise: bool,
    indentation_level: int,
    output_stream: IO[str]
) -> None:
    """Logique pour le mode 'sources_and_deposits' (CLI)."""
    output_stream.write("\n\n============================================================")
    output_stream.write("\n--- LISTING DES SOURCES ET LEURS DÉPÔTS ASSOCIÉS ---")
    output_stream.write("\n============================================================")
    
    total_sources = len(sources_data)
    if total_sources == 0:
        output_stream.write("[INFO] Aucune source (SOUR) trouvée pour lier les dépôts.\n")
        return

    sorted_source_keys = sorted(sources_data.keys(), key=cle_numerique_xref)

    for numero_source, identifiant in enumerate(sorted_source_keys, start=1):
        data = sources_data[identifiant]
        source = data["node"]
        deposits_xrefs = data["deposit_xrefs"]
        
        output_stream.write(f"\n\n{'='*10} SOURCE {numero_source}/{total_sources} : {identifiant} {'='*10}\n")
        output_stream.write("-" * 80 + "\n")

        # 1. Affiche la source complète (SOUR)
        output_stream.write("\n[--> SOURCE COMPLÈTE]\n")
        afficher_arbre(source, colorise=colorise, indentation_level=indentation_level, output_stream=output_stream)
        _afficher_notes_associees(data["note_references"], colorise, indentation_level, output_stream)
        
        # 2. Affichage des dépôts associés (REPO)
        if deposits_xrefs:
            output_stream.write(f"\n\n{'=' * 20} DÉPÔTS ASSOCIÉS ({len(deposits_xrefs)}) {'='*20}\n")
            for xref in deposits_xrefs:
                repo_node_complet = xref_map.get(xref)
                if repo_node_complet:
                    output_stream.write(f"\n--- DÉPOT COMPLET : {xref} ---\n")
                    niveau_depot = indentation_level if indentation_level < 0 else indentation_level + 1
                    afficher_arbre(repo_node_complet, colorise=colorise, indentation_level=niveau_depot, output_stream=output_stream)
                else:
                    output_stream.write(f"\n[ATTENTION] Dépôt {xref} référencé mais non trouvé dans xref_map.\n")
        else:
            output_stream.write(f"\n[INFO] Aucun dépôt (REPO) référencé pour cette source.\n")


def _lister_sources_et_citations(
    sources_data: SourcesData,
    citations: Dict[str, List[Citation]],
    colorise: bool,
    indentation_level: int,
    output_stream: IO[str]
) -> None:
    """Logique pour le mode 'sources_and_citations' (CLI)."""
    output_stream.write("\n\n============================================================")
    output_stream.write("\n--- LISTING DES SOURCES ET LEURS CITATIONS ASSOCIÉES ---")
    output_stream.write("\n============================================================")

    total_sources = len(sources_data)
    if total_sources == 0:
        output_stream.write("[INFO] Aucune source (SOUR) trouvée pour analyser les citations.\n")
        return
        
    sorted_source_keys = sorted(sources_data.keys(), key=cle_numerique_xref)
    
    for numero_source, identifiant in enumerate(sorted_source_keys, start=1):
        data = sources_data[identifiant]
        source = data["node"]
        
        output_stream.write(f"\n\n{'='*10} SOURCE {numero_source}/{total_sources} : {identifiant} {'='*10}\n")
        output_stream.write("-" * 80 + "\n")

        # 1. Affiche la source complète (SOUR)
        output_stream.write("\n[--> SOURCE COMPLÈTE]\n")
        afficher_arbre(source, colorise=colorise, indentation_level=indentation_level, output_stream=output_stream)
        
        # 2. Affichage des citations qui pointent VERS cette Source (Source est la cible)
        citations_associees = citations.get(identifiant, [])
        note_references_groupe = regrouper_notes_associees(
            data["note_references"], citations_associees
        )

        if citations_associees:
            output_stream.write(f"\n\n{'=' * 20} CITATIONS POINTANT VERS CETTE SOURCE ({len(citations_associees)}) {'='*20}\n")
            for numero_citation, (citation, racine, note_references) in enumerate(citations_associees, start=1):
                contexte = ancetre_evenement(citation, racine)
                output_stream.write(f"\n--- CITATION {numero_citation}/{len(citations_associees)} ---\n")
                output_stream.write(f"Contexte d'apparition: {contexte}\n")
                afficher_arbre(citation, colorise=colorise, indentation_level=indentation_level, output_stream=output_stream)
        else:
            output_stream.write("\n[INFO] Aucune citation trouvée pointant vers cette source.\n")
        cible_notes = "cette source et ses citations" if citations_associees else "cette source"
        _afficher_notes_associees(note_references_groupe, colorise, indentation_level, output_stream, cible_notes)


def _afficher_rapport_complet(
    sources_data: SourcesData,
    xref_map: Dict[str, GedcomNode],
    citations: Dict[str, List[Citation]],
    colorise: bool,
    indentation_level: int,
    output_stream: IO[str],
) -> None:
    """Affiche chaque source avec ses notes, dépôts et citations associés."""
    output_stream.write("\n\n============================================================")
    output_stream.write("\n--- LISTING DES SOURCES, DÉPÔTS ET CITATIONS ---")
    output_stream.write("\n============================================================")

    total_sources = len(sources_data)
    if total_sources == 0:
        output_stream.write("[INFO] Aucune source (SOUR) trouvée.\n")
        return

    sorted_source_keys = sorted(sources_data.keys(), key=cle_numerique_xref)
    for numero_source, identifiant in enumerate(sorted_source_keys, start=1):
        data = sources_data[identifiant]
        source = data["node"]
        deposits_xrefs = data["deposit_xrefs"]

        output_stream.write(f"\n\n{'=' * 10} SOURCE {numero_source}/{total_sources} : {identifiant} {'=' * 10}\n")
        output_stream.write("-" * 80 + "\n")
        output_stream.write("\n[--> SOURCE COMPLÈTE]\n")
        afficher_arbre(source, colorise=colorise, indentation_level=indentation_level, output_stream=output_stream)
        citations_associees = citations.get(identifiant, [])
        note_references_groupe = regrouper_notes_associees(
            data["note_references"], citations_associees
        )

        if deposits_xrefs:
            output_stream.write(f"\n\n{'=' * 20} DÉPÔTS ASSOCIÉS ({len(deposits_xrefs)}) {'=' * 20}\n")
            for xref in deposits_xrefs:
                repo_node = xref_map.get(xref)
                if repo_node:
                    output_stream.write(f"\n--- DÉPOT COMPLET : {xref} ---\n")
                    niveau_depot = indentation_level if indentation_level < 0 else indentation_level + 1
                    afficher_arbre(repo_node, colorise=colorise, indentation_level=niveau_depot, output_stream=output_stream)
                else:
                    output_stream.write(f"\n[ATTENTION] Dépôt {xref} référencé mais non trouvé dans xref_map.\n")
        else:
            output_stream.write("\n[INFO] Aucun dépôt (REPO) référencé pour cette source.\n")

        if citations_associees:
            output_stream.write(f"\n\n{'=' * 20} CITATIONS POINTANT VERS CETTE SOURCE ({len(citations_associees)}) {'=' * 20}\n")
            for numero_citation, (citation, racine, note_references) in enumerate(citations_associees, start=1):
                contexte = ancetre_evenement(citation, racine)
                output_stream.write(f"\n--- CITATION {numero_citation}/{len(citations_associees)} ---\n")
                output_stream.write(f"Contexte d'apparition: {contexte}\n")
                afficher_arbre(citation, colorise=colorise, indentation_level=indentation_level, output_stream=output_stream)
        else:
            output_stream.write("\n[INFO] Aucune citation trouvée pointant vers cette source.\n")
        cible_notes = "cette source et ses citations" if citations_associees else "cette source"
        _afficher_notes_associees(note_references_groupe, colorise, indentation_level, output_stream, cible_notes)


# =================================================================
# --- FONCTION PRINCIPALE (LE ROUTEUR) ---
# =================================================================

def afficher_rapport(
    xref_map: Dict[str, GedcomNode],
    colorise: bool,
    mode: str,
    indentation_level: int,
    sources_data: SourcesData,
    citations: Dict[str, List[Citation]],
    output_stream=sys.stdout,
    nom_fichier: Optional[str] = None,
) -> None:
    """Sélectionne le rendu texte correspondant au mode demandé."""

    if nom_fichier:
        output_stream.write(f"Fichier GEDCOM analysé : {nom_fichier}\n\n")
    
    if mode == "sources":
        _lister_sources(sources_data, colorise, indentation_level, output_stream)
    
    elif mode == "depots":
        _lister_depots(xref_map, colorise, indentation_level, output_stream)
        
    elif mode == "citations":
        _lister_citations(citations, sources_data, colorise, indentation_level, output_stream)
        
    elif mode == "sources_and_deposits":
        _lister_sources_et_depots(sources_data, xref_map, colorise, indentation_level, output_stream)
        
    elif mode == "sources_and_citations":
        _lister_sources_et_citations(sources_data, citations, colorise, indentation_level, output_stream)
    
    elif mode == "all":
        _afficher_rapport_complet(sources_data, xref_map, citations, colorise, indentation_level, output_stream)
