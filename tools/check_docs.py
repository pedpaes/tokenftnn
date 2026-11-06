"""Verifica links relativos nos arquivos Markdown do projeto.

Links externos (`http`, `https`, `mailto`) e âncoras internas (`#secao`) são
ignorados. Links dentro de blocos de código e de trechos entre crases também
são ignorados, para não confundir exemplos com documentação real.

Uso:
    .droxz\\Scripts\\python.exe tools\\check_docs.py
    .droxz\\Scripts\\python.exe tools\\check_docs.py --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent

_LINK_RE = re.compile(r"!?\[[^\]]*\]\(\s*([^)\s]+)(?:\s+[\"'][^\"']*[\"'])?\s*\)")
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
_IGNORED_DIRS = {".git", ".droxz", "__pycache__", "logs", "assets"}


@dataclass(frozen=True)
class LinkIssue:
    source: str
    line: int
    target: str
    reason: str


def discover_markdown(root: Path = ROOT) -> list[Path]:
    """Lista os Markdown versionáveis do projeto em ordem estável."""
    files: list[Path] = []
    for path in root.rglob("*.md"):
        if any(part in _IGNORED_DIRS for part in path.relative_to(root).parts):
            continue
        files.append(path)
    return sorted(files)


def _strip_code(line: str) -> str:
    """Remove trechos entre crases para não interpretar exemplos como links."""
    return re.sub(r"`[^`]*`", "", line)


def _iter_links(text: str):
    """Gera (linha, alvo) de links Markdown fora de blocos de código."""
    in_fence = False
    fence_marker = ""
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            marker = stripped[:3]
            if not in_fence:
                in_fence = True
                fence_marker = marker
            elif marker == fence_marker:
                in_fence = False
                fence_marker = ""
            continue
        if in_fence:
            continue
        for match in _LINK_RE.finditer(_strip_code(line)):
            yield number, match.group(1)


def _resolve(source: Path, target: str, root: Path) -> Path | None:
    clean = target.strip()
    if clean.startswith("<") and clean.endswith(">"):
        clean = clean[1:-1]
    if not clean or clean.startswith("#"):
        return None
    if _SCHEME_RE.match(clean):
        return None

    clean = unquote(clean.split("#", 1)[0])
    if not clean:
        return None
    if clean.startswith("/"):
        return root / clean.lstrip("/")
    return source.parent / clean


def check_file(path: Path, root: Path = ROOT) -> list[LinkIssue]:
    """Confere todos os links relativos de um arquivo Markdown."""
    text = path.read_text(encoding="utf-8")
    issues: list[LinkIssue] = []
    for line, target in _iter_links(text):
        resolved = _resolve(path, target, root)
        if resolved is None:
            continue
        if not resolved.exists():
            issues.append(
                LinkIssue(
                    source=str(path.relative_to(root)),
                    line=line,
                    target=target,
                    reason="destino não encontrado",
                )
            )
    return issues


def check_all(root: Path = ROOT) -> tuple[list[Path], list[LinkIssue]]:
    files = discover_markdown(root)
    issues: list[LinkIssue] = []
    for path in files:
        issues.extend(check_file(path, root))
    return files, issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verifica links relativos da documentação Markdown."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Imprime o resultado em JSON.",
    )
    args = parser.parse_args(argv)

    files, issues = check_all()
    if args.json:
        print(
            json.dumps(
                {
                    "files": [str(path.relative_to(ROOT)) for path in files],
                    "issues": [asdict(issue) for issue in issues],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"Documentação verificada: {len(files)} arquivo(s) Markdown.")
        if issues:
            for issue in issues:
                print(
                    f"{issue.source}:{issue.line}: {issue.target} "
                    f"({issue.reason})",
                    file=sys.stderr,
                )
            print(f"{len(issues)} link(s) quebrado(s).", file=sys.stderr)
        else:
            print("Todos os links relativos estão válidos.")

    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
