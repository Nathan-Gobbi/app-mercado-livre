#!/usr/bin/env python3
"""Create a consistently named development branch from 18.0."""

import re
import subprocess
import sys


TYPES = {"feature", "fix", "refactor", "docs", "chore"}
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def git(*arguments):
    return subprocess.run(
        ["git", *arguments], check=True, capture_output=True, text=True
    ).stdout.strip()


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in TYPES or not SLUG_RE.fullmatch(
        sys.argv[2]
    ):
        types = "|".join(sorted(TYPES))
        raise SystemExit(
            f"Uso: {sys.argv[0]} <{types}> <descricao-em-minusculas>"
        )
    if git("status", "--porcelain"):
        raise SystemExit("A árvore de trabalho deve estar limpa antes de criar a branch.")
    branch = f"18.0-{sys.argv[1]}-{sys.argv[2]}"
    git("switch", "18.0")
    git("switch", "-c", branch)
    print(f"Branch criada: {branch}")


if __name__ == "__main__":
    main()
