#!/usr/bin/env python3
"""Add one entry to the unreleased section of CHANGELOG.md."""

from pathlib import Path
import sys


CATEGORIES = {
    "added": "Adicionado",
    "changed": "Alterado",
    "fixed": "Corrigido",
    "removed": "Removido",
}
CHANGELOG = Path(__file__).resolve().parents[1] / "CHANGELOG.md"


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in CATEGORIES:
        choices = "|".join(CATEGORIES)
        raise SystemExit(f'Uso: {sys.argv[0]} <{choices}> "resumo"')
    summary = sys.argv[2].strip().rstrip(".")
    if not summary:
        raise SystemExit("O resumo não pode ficar vazio.")
    heading = f"### {CATEGORIES[sys.argv[1]]}\n"
    content = CHANGELOG.read_text()
    position = content.find(heading, content.find("## [Não publicado]"))
    if position < 0:
        raise SystemExit(f"Seção não encontrada: {heading.strip()}")
    insertion = position + len(heading)
    entry = f"\n- {summary}."
    if entry in content:
        raise SystemExit("Essa entrada já existe no changelog.")
    CHANGELOG.write_text(content[:insertion] + entry + content[insertion:])
    print(f"CHANGELOG.md atualizado em {CATEGORIES[sys.argv[1]]}.")


if __name__ == "__main__":
    main()
