import io
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

import main
from gedcom.analyzer import indexer_entites, trouver_citations, trouver_sources_et_depots
from gedcom.html_reporter import generer_rapport_html
from gedcom.parser import analyser_lignes, construire_xref_map, lire_fichier
from gedcom.text_reporter import afficher_rapport


class GedcomPipelineTests(unittest.TestCase):
    def setUp(self):
        self.roots = analyser_lignes([
            "0 HEAD",
            "1 SOUR TEST",
            "0 @S1@ SOUR",
            "1 TITL Archives <script>alert(1)</script>",
            "1 WWW https://example.test/path?a=1&b=2.",
            "1 WWW http://example.test/legacy.",
            "1 NOTE @R1@",
            "1 NOTE @N1@",
            "1 NOTE Note inline conservée dans la source",
            "1 REPO @R1@",
            "0 @R1@ REPO",
            "1 NAME Archives départementales",
            "0 @N1@ NOTE",
            "1 CONT Une note complète référencée",
            "0 @I1@ INDI",
            "1 FAMC @F1@",
            "1 SOUR @S1@",
            "2 NOTE @N1@",
            "0 @F1@ FAM",
            "1 SOUR @MISSING@",
        ])
        self.xref_map = indexer_entites(self.roots, "REPO")
        self.sources_data = trouver_sources_et_depots(self.roots, self.xref_map)
        self.citations = trouver_citations(self.roots)

    def test_lire_fichier_detecte_utf8_avec_bom(self):
        with tempfile.TemporaryDirectory() as dossier:
            path = Path(dossier) / "utf8.ged"
            path.write_bytes(b"\xef\xbb\xbf0 HEAD\n1 NOTE caf\xc3\xa9\n")

            self.assertEqual(lire_fichier(path), ["0 HEAD", "1 NOTE café"])

    def test_lire_fichier_accepte_un_encodage_explicite(self):
        with tempfile.TemporaryDirectory() as dossier:
            path = Path(dossier) / "cp1252.ged"
            path.write_bytes("0 HEAD\n1 NOTE café\n".encode("cp1252"))

            self.assertEqual(
                lire_fichier(path, "cp1252"),
                ["0 HEAD", "1 NOTE café"],
            )

    def test_cli_refuse_un_repertoire_comme_fichier_gedcom(self):
        with tempfile.TemporaryDirectory() as dossier:
            erreur = io.StringIO()
            with patch("sys.argv", ["main.py", dossier]), redirect_stderr(erreur):
                with self.assertRaises(SystemExit) as sortie:
                    main.main()

        self.assertEqual(sortie.exception.code, 1)
        self.assertIn("le chemin indiqué n'est pas un fichier", erreur.getvalue())

    def test_analyser_lignes_construit_les_liens_parent_enfant(self):
        source = next(root for root in self.roots if root.xref == "@S1@")
        titre = source.children[0]

        self.assertEqual(source.tag, "SOUR")
        self.assertIs(titre.parent, source)
        self.assertEqual(titre.value, "Archives <script>alert(1)</script>")

    def test_analyser_lignes_signale_et_ignore_une_ligne_invalide(self):
        erreur = io.StringIO()
        with redirect_stderr(erreur):
            roots = analyser_lignes(["0 HEAD", "ligne invalide"])

        self.assertEqual([root.tag for root in roots], ["HEAD"])
        self.assertIn("ligne GEDCOM ignorée (2)", erreur.getvalue())

    def test_analyser_lignes_signale_et_ignore_saut_de_niveau(self):
        erreur = io.StringIO()
        with redirect_stderr(erreur):
            roots = analyser_lignes([
                "0 HEAD",
                "2 NOTE niveau manquant",
                "1 NOTE ligne valide",
            ])

        self.assertEqual([child.value for child in roots[0].children], ["ligne valide"])
        self.assertIn("saut de niveau invalide à la ligne 2", erreur.getvalue())

    def test_analyser_lignes_signale_les_xref_dupliques(self):
        erreur = io.StringIO()
        with redirect_stderr(erreur):
            roots = analyser_lignes([
                "0 @R1@ REPO",
                "1 NAME Première version",
                "0 @R1@ REPO",
                "1 NAME Dernière version",
            ])

        xref_map = indexer_entites(roots, "REPO")
        self.assertIn("XREF dupliqué @R1@ aux lignes 1 et 3", erreur.getvalue())
        self.assertEqual(xref_map["@R1@"].children[0].value, "Dernière version")

    def test_indexe_uniquement_les_enregistrements_repo(self):
        self.assertEqual(list(self.xref_map), ["@R1@"])
        self.assertEqual(self.xref_map["@R1@"].tag, "REPO")
        self.assertEqual(construire_xref_map(self.roots), self.xref_map)

    def test_associe_le_depot_a_la_source(self):
        self.assertEqual(self.sources_data["@S1@"]["deposit_xrefs"], ["@R1@"])

    def test_associe_les_references_note_existantes_a_la_source(self):
        notes = self.sources_data["@S1@"]["note_references"]

        self.assertEqual([(reference.value, root.xref, note.xref) for reference, root, note in notes], [("@N1@", "@S1@", "@N1@")])

    def test_mode_sources_et_depots_affiche_les_notes_referencees(self):
        output = io.StringIO()
        afficher_rapport(
            self.xref_map,
            colorise=False,
            mode="sources_and_deposits",
            indentation_level=-1,
            sources_data=self.sources_data,
            citations=self.citations,
            output_stream=output,
        )

        self.assertIn("NOTES RÉFÉRENCÉES (1)", output.getvalue())
        self.assertIn("Contexte d'apparition: @S1@ SOUR > NOTE", output.getvalue())

    def test_signale_l_absence_de_notes_dans_les_rapports(self):
        roots = analyser_lignes(["0 @S2@ SOUR", "1 TITL Source sans note"])
        sources_data = trouver_sources_et_depots(roots, {})
        output = io.StringIO()
        afficher_rapport(
            {},
            colorise=False,
            mode="all",
            indentation_level=-1,
            sources_data=sources_data,
            citations={},
            output_stream=output,
        )
        assets_dir = Path(__file__).resolve().parents[1] / "web"
        html_report = generer_rapport_html(sources_data, {}, {}, assets_dir)

        self.assertIn(
            "-" * 80 + "\nAucune note trouvée pointant vers cette source.",
            output.getvalue(),
        )
        self.assertIn(
            '<hr style="border: 0; border-top: 1px solid var(--line); margin: 28px 0;">\n'
            '<div class="note-panel"><p>Aucune note trouvée pointant vers cette source.</p></div>',
            html_report,
        )

    def test_ne_compte_que_les_references_sour_comme_citations(self):
        self.assertEqual(list(self.citations), ["@S1@", "@MISSING@"])
        self.assertEqual(self.citations["@S1@"][0][0].tag, "SOUR")

    def test_associe_les_references_note_a_une_citation(self):
        note_references = self.citations["@S1@"][0][2]

        self.assertEqual(
            [(reference.value, root.xref, note.xref) for reference, root, note in note_references],
            [("@N1@", "@I1@", "@N1@")],
        )

    def test_rapport_texte_contient_source_depot_et_citation(self):
        output = io.StringIO()
        afficher_rapport(
            self.xref_map,
            colorise=False,
            mode="all",
            indentation_level=-1,
            sources_data=self.sources_data,
            citations=self.citations,
            output_stream=output,
            nom_fichier="archives & family.ged",
        )

        report = output.getvalue()
        self.assertIn("Fichier GEDCOM analysé : archives & family.ged", report)
        self.assertIn("@S1@", report)
        self.assertIn("DÉPOT COMPLET : @R1@", report)
        self.assertEqual(report.count("NOTES RÉFÉRENCÉES (2)"), 1)
        self.assertIn("--- NOTE 1/2 ---", report)
        self.assertIn("--- NOTE 2/2 ---", report)
        self.assertIn("-" * 80, report)
        self.assertIn("Contexte d'apparition: @S1@ SOUR > NOTE", report)
        self.assertIn("Contexte d'apparition: @S1@ SOUR > NOTE\n0 @N1@ NOTE", report)
        self.assertNotIn("Entité NOTE complète", report)
        self.assertIn("Une note complète référencée", report)
        self.assertIn("CITATIONS POINTANT VERS CETTE SOURCE", report)
        self.assertIn("NOTES RÉFÉRENCÉES (2)", report)
        self.assertIn("Contexte d'apparition: @I1@ INDI > SOUR > NOTE", report)

        citations_output = io.StringIO()
        afficher_rapport(
            self.xref_map,
            colorise=False,
            mode="citations",
            indentation_level=-1,
            sources_data=self.sources_data,
            citations=self.citations,
            output_stream=citations_output,
        )
        self.assertEqual(citations_output.getvalue().count("NOTES RÉFÉRENCÉES (2)"), 1)

        sources_and_citations_output = io.StringIO()
        afficher_rapport(
            self.xref_map,
            colorise=False,
            mode="sources_and_citations",
            indentation_level=-1,
            sources_data=self.sources_data,
            citations=self.citations,
            output_stream=sources_and_citations_output,
        )
        self.assertEqual(
            sources_and_citations_output.getvalue().count("NOTES RÉFÉRENCÉES (2)"),
            1,
        )

    def test_rapport_html_echappe_le_contenu_gedcom(self):
        assets_dir = Path(__file__).resolve().parents[1] / "web"
        report = generer_rapport_html(
            self.sources_data,
            self.xref_map,
            self.citations,
            assets_dir,
            nom_fichier="archives&family.ged",
        )

        self.assertIn("Fichier GEDCOM analysé : archives&amp;family.ged", report)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", report)
        self.assertNotIn("Archives <script>alert(1)</script>", report)
        self.assertIn(
            '<a href="https://example.test/path?a=1&amp;b=2" target="_blank" '
            'rel="noopener noreferrer">https://example.test/path?a=1&amp;b=2</a>.',
            report,
        )
        self.assertIn(
            '<a href="http://example.test/legacy" target="_blank" '
            'rel="noopener noreferrer">http://example.test/legacy</a>.',
            report,
        )
        self.assertNotIn("DÉPÔTS ASSOCIÉS", report)
        self.assertIn('<h4 style="margin-top: 0;">SOURCE COMPLÈTE</h4>', report)
        self.assertIn('<h4 style="margin-top: 0;">DÉPÔT COMPLET : @R1@</h4>', report)
        self.assertEqual(report.count("NOTES RÉFÉRENCÉES (2)"), 1)
        self.assertIn(
            'Contexte d\'apparition: @S1@ SOUR &gt; NOTE</p>\n<div class="line-output"><span class="color-grey">0</span> <span class="color-cyan">@N1@</span> <span class="color-yellow">NOTE</span>',
            report,
        )
        self.assertIn('<hr style="border: 0; border-top: 1px solid var(--line); margin: 28px 0;">', report)
        self.assertNotIn("ENTITÉ NOTE COMPLÈTE", report)
        self.assertIn("Une note complète référencée", report)
        self.assertEqual(report.count("NOTES RÉFÉRENCÉES (2)"), 1)
        self.assertIn("--- NOTE 1/2 ---", report)
        self.assertIn("--- NOTE 2/2 ---", report)
        self.assertIn("@I1@ INDI &gt; SOUR &gt; NOTE", report)
        self.assertIn('id="first-btn"', report)
        self.assertIn('id="last-btn"', report)
        self.assertIn("firstBtn.addEventListener('click'", report)
        self.assertIn("lastBtn.addEventListener('click'", report)
        self.assertIn("flex-wrap: nowrap;", report)
        self.assertIn('id="prev-page-btn"', report)
        self.assertIn('id="next-page-btn"', report)
        self.assertIn('<select id="page-step" aria-label="Nombre de sources par saut">', report)
        for step in (10, 20, 30, 40, 50):
            self.assertIn(f'<option value="{step}"', report)
        self.assertIn('<option value="10" selected>10</option>', report)
        self.assertIn('id="auto-scroll-citations" type="checkbox"', report)
        self.assertIn("autoScrollCitationsCheckbox.checked", report)
        self.assertIn("scrollToCitations();", report)
        self.assertIn('id="auto-scroll-notes" type="checkbox"', report)
        self.assertIn("Aller aux notes à chaque changement de source", report)
        self.assertIn("autoScrollNotesCheckbox.checked", report)
        self.assertIn("scrollToNotes();", report)
        self.assertIn("autoScrollCitationsCheckbox.checked = false", report)
        self.assertIn("Math.max(0, targetScrollTop - maxScrollTop)", report)
        self.assertIn("contentArea.style.paddingBottom = `${extraBottomSpace}px`", report)
        self.assertIn("overflow: hidden;", report)
        self.assertIn("overflow-y: auto;", report)
        self.assertIn('id="content-area" tabindex="0"', report)
        self.assertIn('</nav>\n        </header>\n        <div class="report-options">', report)
        self.assertIn('</label>\n        </div>\n        <div class="progress-track"', report)
        source_position = report.index('class="source-panel"')
        deposit_position = report.index('class="deposit-panel"')
        citations_position = report.index('class="citations-panel"')
        self.assertLess(source_position, deposit_position)
        self.assertLess(deposit_position, citations_position)


if __name__ == "__main__":
    unittest.main()