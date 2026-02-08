#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import os
import sys
from dataclasses import dataclass
from typing import Iterable, List, Set, Tuple

# Fail-closed: only INTERNAL cross-zone imports are enforced.
# Stdlib / third-party imports are ignored.
# Relative imports are treated as same-zone.

@dataclass
class Finding:
    rule_id: str
    file: str
    line: int
    msg: str
    snippet: str


def _norm(p: str) -> str:
    return p.replace("\\", "/")


def _walk_py_files(root: str) -> Iterable[str]:
    for dirpath, dirnames, filenames in os.walk(root):
        dn = _norm(dirpath)
        if any(x in f"/{dn}/" for x in ("/.git/", "/.venv/", "/venv/", "/__pycache__/")):
            continue
        for fn in filenames:
            if fn.endswith(".py"):
                yield os.path.join(dirpath, fn)


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _parse_imports(py_src: str) -> List[Tuple[int, str]]:
    """
    Returns (lineno, module) for import and from-import.
    """
    out: List[Tuple[int, str]] = []
    tree = ast.parse(py_src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.append((getattr(node, "lineno", 1), a.name))
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                out.append((getattr(node, "lineno", 1), "<RELATIVE_IMPORT>"))
            else:
                mod = node.module
                if node.level:
                    mod = "." * node.level + mod
                out.append((getattr(node, "lineno", 1), mod))
    return out


# ---- Zones ----
ZONE_ORCH = "orchestrator"
ZONE_GATE = "gate"
ZONE_VAULT = "vault"
ZONE_BRAIN = "brain"
ZONE_UNKNOWN = "unknown"


def _zone_for_file(relpath: str) -> str:
    rp = _norm(relpath)
    if rp.startswith("orchestrator/"):
        return ZONE_ORCH
    if rp.startswith(("tools/gates/", "core/gate/", "gate/")):
        return ZONE_GATE
    if rp.startswith(("vault/", "core/vault/")):
        return ZONE_VAULT
    if rp.startswith(("core/brain/", "core/domain/", "brain/", "domain/")):
        return ZONE_BRAIN
    return ZONE_UNKNOWN


IMPORT_PREFIX_TO_ZONE = [
    ("vault", ZONE_VAULT),
    ("core.vault", ZONE_VAULT),
    ("tools.gates", ZONE_GATE),
    ("core.gate", ZONE_GATE),
    ("gate", ZONE_GATE),
    ("orchestrator", ZONE_ORCH),
    ("core.brain", ZONE_BRAIN),
    ("core.domain", ZONE_BRAIN),
    ("brain", ZONE_BRAIN),
    ("domain", ZONE_BRAIN),
]


def _is_relative(mod: str) -> bool:
    return mod.startswith(".") or mod == "<RELATIVE_IMPORT>"


def _is_internal_module(mod: str) -> bool:
    if mod in ("<RELATIVE_IMPORT>", "<UNKNOWN>"):
        return False
    m = mod.lstrip(".")
    for prefix, _z in IMPORT_PREFIX_TO_ZONE:
        if m == prefix or m.startswith(prefix + "."):
            return True
    return False


def _zone_for_import(mod: str) -> str:
    if mod in ("<RELATIVE_IMPORT>", "<UNKNOWN>"):
        return ZONE_UNKNOWN
    m = mod.lstrip(".")
    for prefix, z in IMPORT_PREFIX_TO_ZONE:
        if m == prefix or m.startswith(prefix + "."):
            return z
    return ZONE_UNKNOWN


FORBIDDEN_EDGES: Set[Tuple[str, str]] = {
    (ZONE_ORCH, ZONE_VAULT),
    (ZONE_ORCH, ZONE_BRAIN),
    (ZONE_BRAIN, ZONE_VAULT),
    (ZONE_BRAIN, ZONE_GATE),
    (ZONE_BRAIN, ZONE_ORCH),
    (ZONE_VAULT, ZONE_GATE),
    (ZONE_VAULT, ZONE_ORCH),
    (ZONE_VAULT, ZONE_BRAIN),
}


def _print_findings(findings: List[Finding]) -> None:
    for f in findings:
        print(
            f"FAIL {f.rule_id} file={f.file} line={f.line} "
            f"msg={f.msg} snippet={f.snippet}"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description="Zone Static Gate (fail-closed)")
    ap.add_argument("--root", default=".", help="Repo root")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    findings: List[Finding] = []

    zone_doc = os.path.join(root, "docs/architecture/AURALIS_ZONE_MAP.md")
    if not os.path.exists(zone_doc):
        findings.append(
            Finding(
                "ZONE_MAP_MISSING",
                "docs/architecture/AURALIS_ZONE_MAP.md",
                1,
                "Zone map must exist for enforcement",
                "missing",
            )
        )
        _print_findings(findings)
        return 1

    for abspath in _walk_py_files(root):
        rel = _norm(os.path.relpath(abspath, root))
        file_zone = _zone_for_file(rel)

        try:
            src = _read_text(abspath)
            imports = _parse_imports(src)
        except Exception as e:
            findings.append(
                Finding(
                    "ZONE_PARSE_FAIL",
                    rel,
                    1,
                    "Failed to parse file (fail-closed)",
                    f"{type(e).__name__}:{e}",
                )
            )
            continue

        for lineno, mod in imports:
            if _is_relative(mod):
                continue
            if not _is_internal_module(mod):
                continue

            imp_zone = _zone_for_import(mod)

            if file_zone != ZONE_UNKNOWN and imp_zone == ZONE_UNKNOWN:
                findings.append(
                    Finding(
                        "ZONE_INTERNAL_IMPORT_UNCLASSIFIED",
                        rel,
                        lineno,
                        "Internal import could not be classified into a zone",
                        mod,
                    )
                )
                continue

            if (file_zone, imp_zone) in FORBIDDEN_EDGES:
                findings.append(
                    Finding(
                        "ZONE_EDGE_FORBIDDEN",
                        rel,
                        lineno,
                        "Forbidden zone dependency detected",
                        f"{file_zone} -> {imp_zone} via {mod}",
                    )
                )

    if findings:
        _print_findings(findings)
        return 1

    print("PASS ZONE_STATIC_GATE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
