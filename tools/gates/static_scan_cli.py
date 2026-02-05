from __future__ import annotations
import argparse
from pathlib import Path
from tools.gates.static_scan import scan_tree

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", help="root directory to scan")
    args = ap.parse_args()

    findings = scan_tree(Path(args.root))
    if findings:
        print("FAIL-CLOSED: static scan findings detected")
        for f in findings:
            print(f"- {f.rule_id} | {f.file}:{f.line} | {f.snippet}")
        return 1

    print("OK: static scan clean")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
