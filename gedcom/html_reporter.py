"""Assemblage du rapport HTML autonome à partir des données analysées."""

import re
from html import escape
from pathlib import Path
from typing import Dict, List, Optional

from .analyzer import Citation, SourcesData, regrouper_notes_associees
from .utils import GedcomNode, ancetre_evenement, cle_numerique_xref, est_reference_gedcom


URL_RE = re.compile(r"https?://[^\s<>\"']+")


def _rendre_liens_url(valeur: str) -> str:
    """Échappe une valeur et transforme ses URL HTTP(S) en liens sûrs."""
    morceaux = []
    position = 0

    for match in URL_RE.finditer(valeur):
        url = match.group().rstrip(".,;:!?)]}")
        if not url:
            continue
        debut_url = match.start()
        fin_url = debut_url + len(url)
        morceaux.append(escape(valeur[position:debut_url]))
        url_echappee = escape(url)
        morceaux.append(
            f'<a href="{url_echappee}" target="_blank" rel="noopener noreferrer">'
            f"{url_echappee}</a>"
        )
        morceaux.append(escape(valeur[fin_url:match.end()]))
        position = match.end()

    morceaux.append(escape(valeur[position:]))
    return "".join(morceaux)


def _convertir_valeur_en_html(node: GedcomNode) -> str:
    """Échappe et colore la valeur d'un nœud GEDCOM."""
    valeur = _rendre_liens_url(node.value)
    if est_reference_gedcom(node.value):
        return f'<span class="color-green">{valeur}</span>'
    if node.tag == "REPO" and node.value:
        return f'<span class="color-magenta">{valeur}</span>'
    return f'<span class="color-white">{valeur}</span>'


def _rendre_arbre_en_html(node: GedcomNode, indentation: str = "") -> str:
    """Rend un nœud GEDCOM et ses descendants en lignes HTML."""
    level_html = f'<span class="color-grey">{node.level}</span>'
    xref_html = f'<span class="color-cyan">{escape(node.xref)}</span>' if node.xref else ""
    tag_html = f'<span class="color-yellow">{escape(node.tag)}</span>'
    value_html = _convertir_valeur_en_html(node) if node.value else ""
    line_content = f"{tag_html}{' ' if value_html else ''}{value_html}"
    line = f'<div class="line-output">{indentation}{level_html} {xref_html} {line_content}</div>'
    children = "".join(_rendre_arbre_en_html(child, indentation + "  ") for child in node.children)
    return line + children


def generer_rapport_html(
    sources_data: SourcesData,
    xref_map: Dict[str, GedcomNode],
    citations: Dict[str, List[Citation]],
    assets_dir: Path,
    nom_fichier: Optional[str] = None,
) -> str:
    """Assemble un rapport HTML contenant une section par source."""
    sections = []
    sorted_source_keys = sorted(sources_data, key=cle_numerique_xref)

    for numero_source, identifiant in enumerate(sorted_source_keys, start=1):
        data = sources_data[identifiant]
        source = data["node"]
        deposit_xrefs = data["deposit_xrefs"]
        source_citations = citations.get(identifiant, [])
        note_references = regrouper_notes_associees(data["note_references"], source_citations)
        section = [
            f'<h3 style="margin-top: 0;">Source {numero_source}/{len(sorted_source_keys)} : {escape(identifiant)}</h3>',
            '<div class="source-repository-layout">',
            '<div class="source-panel">',
            '<h4 style="margin-top: 0;">SOURCE COMPLÈTE</h4>',
            _rendre_arbre_en_html(source),
            '</div>',
            '<div class="deposit-panel">',
        ]

        if deposit_xrefs:
            for xref in deposit_xrefs:
                repo_node = xref_map.get(xref)
                if repo_node:
                    section.append(f'<h4 style="margin-top: 0;">DÉPÔT COMPLET : {escape(xref)}</h4>')
                    section.append(_rendre_arbre_en_html(repo_node))
                else:
                    section.append(f'<p style="color: orange;">[ATTENTION] Dépôt {escape(xref)} référencé mais non trouvé dans xref_map.</p>')
        else:
            section.append("<p>Aucun dépôt (REPO) référencé pour cette source.</p>")

        section.extend(['</div>', '</div>'])
        section.append('<div class="citations-panel">')
        if source_citations:
            section.append(f'<h4 style="margin-top: 25px;">{"=" * 20} CITATIONS POINTANT VERS CETTE SOURCE ({len(source_citations)}) {"=" * 20}</h4>')
            for numero_citation, (citation, racine, _) in enumerate(source_citations, start=1):
                contexte = escape(ancetre_evenement(citation, racine))
                section.append(f'<h5 style="margin-top: 20px;">--- CITATION {numero_citation}/{len(source_citations)} ---</h5>')
                section.append(f"<p>Contexte d'apparition: {contexte}</p>")
                section.append(_rendre_arbre_en_html(citation))
        else:
            section.append("<p>Aucune citation trouvée pointant vers cette source.</p>")
        section.append('</div>')
        if note_references:
            section.append('<hr style="border: 0; border-top: 1px solid var(--line); margin: 28px 0;">')
            section.append('<div class="note-panel">')
            section.append(f'<h4 style="margin-top: 25px;">{"=" * 20} NOTES RÉFÉRENCÉES ({len(note_references)}) {"=" * 20}</h4>')
            for numero_note, (note_reference, racine_note, note_node) in enumerate(note_references, start=1):
                contexte_note = escape(ancetre_evenement(note_reference, racine_note))
                section.append(f'<h5 style="margin-top: 20px;">--- NOTE {numero_note}/{len(note_references)} ---</h5>')
                section.append(f"<p>Contexte d'apparition: {contexte_note}</p>")
                section.append(_rendre_arbre_en_html(note_node))
            section.append('</div>')
        else:
            section.append('<hr style="border: 0; border-top: 1px solid var(--line); margin: 28px 0;">')
            cible_notes = "cette source et ses citations" if source_citations else "cette source"
            section.append(f'<div class="note-panel"><p>Aucune note trouvée pointant vers {cible_notes}.</p></div>')

        sections.append('<section class="source-section">\n' + "\n".join(section) + "\n</section>")

    template = (assets_dir / "html_template.html").read_text(encoding="utf-8")
    stylesheet = (assets_dir / "style.css").read_text(encoding="utf-8")
    javascript = (assets_dir / "script.js").read_text(encoding="utf-8")
    html_report = template.replace("<!-- CSS INLINE -->", f"<style>\n{stylesheet}\n</style>")
    if nom_fichier:
        fichier_html = (
            '<p class="report-description report-filename">Fichier GEDCOM analysé : '
            f"{escape(nom_fichier)}</p>"
        )
    else:
        fichier_html = ""
    html_report = html_report.replace("<!-- GEDCOM FILE INFO -->", fichier_html)
    html_report = html_report.replace("<!-- LE CONTENU GENERÉ PAR LE SCRIPT VIENDRA ICI -->", "\n\n".join(sections))
    return html_report.replace("<!-- JAVASCRIPT INLINE -->", f"<script>\n{javascript}\n</script>")