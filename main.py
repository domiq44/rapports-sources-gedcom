"""Point d'entrée CLI pour les rapports de sources GEDCOM."""

import argparse
import sys
from pathlib import Path

from gedcom.parser import lire_fichier, analyser_lignes
from gedcom.analyzer import indexer_entites, trouver_sources_et_depots, trouver_citations
from gedcom.text_reporter import afficher_rapport
from gedcom.html_reporter import generer_rapport_html

def main() -> None:
    """Parse les options, analyse le GEDCOM et écrit le rapport demandé."""
    parser = argparse.ArgumentParser(
        description="Analyseur GEDCOM : Liste des sources, dépôts, ou citations."
    )

    parser.add_argument(
        "fichier",
        type=Path,
        help="Chemin du fichier GEDCOM",
    )

    parser.add_argument(
        "--mode",
        choices=[
            "all", "sources", "depots", "citations", 
            "sources_and_deposits", "sources_and_citations", "all-html"
        ],
        default="all",
        help="Mode d'affichage."
    )

    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Désactive la coloration ANSI (uniquement pour les modes texte).",
    )

    parser.add_argument(
        "--indent",
        type=int,
        default=0,
        help="Niveau d'indentation de base pour l'affichage.",
    )

    parser.add_argument(
        "--no-indent",
        action="store_true",
        help="Désactive l'indentation des lignes dans les rapports texte.",
    )

    parser.add_argument(
        "--encoding",
        default="auto",
        help="Encodage du fichier."
    )

    args = parser.parse_args()

    if not args.fichier.exists():
        print(f"Erreur : fichier introuvable : {args.fichier}", file=sys.stderr)
        sys.exit(1)
    if not args.fichier.is_file():
        print(f"Erreur : le chemin indiqué n'est pas un fichier : {args.fichier}", file=sys.stderr)
        sys.exit(1)

    try:
        # 1. Parser (lecture et structuration)
        lignes = lire_fichier(args.fichier, args.encoding)
        racines = analyser_lignes(lignes)
        
        # 2. Indexer les dépôts
        depots_map = indexer_entites(racines, "REPO")

        # 3. Analyser les sources et citations
        sources_data = trouver_sources_et_depots(racines, depots_map)
        citations = trouver_citations(racines)

        # 4. Produire le rapport demandé
        if args.mode == "all-html":
            # --- MODE HTML ---
            print("--- Démarrage de l'assemblage HTML ---")
            
            project_dir = Path(__file__).resolve().parent
            web_dir = project_dir / "web"
            final_html = generer_rapport_html(
                sources_data,
                depots_map,
                citations,
                web_dir,
                nom_fichier=args.fichier.name,
            )
            
            # Sauvegarder le fichier HTML dans le dossier de sortie
            output_path = project_dir / "resultats_html" / "report_all_html.html"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open('w', encoding='utf-8') as f:
                f.write(final_html)
            
            print(f"\n✅ SUCCÈS : Rapport HTML généré à : {output_path}")
            
        else:
            # --- MODE CONSOLE TEXTE CLI (Ancienne logique) ---
            afficher_rapport(
                depots_map,
                colorise=not args.no_color,
                mode=args.mode,
                indentation_level=-1 if args.no_indent else args.indent,
                sources_data=sources_data,
                citations=citations,
                nom_fichier=args.fichier.name,
            )

    except UnicodeDecodeError as erreur:
        print(f"Erreur d'encodage : {erreur}", file=sys.stderr)
        sys.exit(2)

    except Exception as e:
        print(f"Erreur inattendue durant l'analyse : {e}", file=sys.stderr)
        sys.exit(99)

if __name__ == "__main__":
    main()
