"""Modèle de nœud GEDCOM et fonctions de parcours partagées."""

import re
from dataclasses import dataclass, field
from typing import Generator, List, Optional

# --- Modèle GEDCOM ---
@dataclass
class GedcomNode:
    """Nœud GEDCOM avec ses enfants et son parent éventuel."""

    level: int
    xref: Optional[str]
    tag: str
    value: str
    raw_line: str
    children: List["GedcomNode"] = field(default_factory=list)
    parent: Optional["GedcomNode"] = None

    def add_child(self, child: "GedcomNode") -> None:
        """Ajoute un enfant et établit le lien inverse vers ce nœud."""
        child.parent = self
        self.children.append(child)

# --- Regex ---
GEDCOM_LINE_RE = re.compile(
    r"^(\d+)\s+(?:(@\S+@)\s+)?(\S+)(?:\s+(.*))?$"
)

# --- Utilitaires ---
def est_reference_gedcom(valeur: str) -> bool:
    """Indique si une valeur a la forme d'un XREF GEDCOM (`@...@`)."""
    return valeur.startswith("@") and valeur.endswith("@")

def parcourir(node: GedcomNode) -> Generator[GedcomNode, None, None]:
    """Parcourt un arbre en profondeur, nœud parent avant ses enfants."""
    yield node
    for enfant in node.children:
        yield from parcourir(enfant)

def cle_numerique_xref(xref: str) -> int:
    """Extrait le nombre de l'xref (ex: '@S10@' -> 10)."""
    match = re.search(r'\d+', xref)
    if match:
        return int(match.group(0))
    return 0

def ancetre_evenement(node: GedcomNode, racine: GedcomNode) -> str:
    """Construit le chemin de tags entre la racine et une référence GEDCOM."""
    chemin = []
    courant = node
    while courant is not None and courant is not racine:
        chemin.append(courant.tag)
        courant = courant.parent
    chemin.reverse()
    identifiant = racine.xref or ""
    description = f"{identifiant} {racine.tag}".strip()
    if chemin:
        description += " > " + " > ".join(chemin)
    return description

