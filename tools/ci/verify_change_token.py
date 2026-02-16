from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

try:
    import yaml  # type: ignore
except Exception as e:
    print("ERROR: pyyaml is required for tools.ci.verify_change_token", file=sys.stderr)
    raise


TOKENS = ["A-PATCH", "A-MINOR", "A-MAJOR"]
TOKEN_RANK = {t: i for i, t in enumerate(TOKENS)}  # PATCH=0, MINOR=1, MAJOR=2


def _run(cmd: list[str], cwd: Optional[Path] = None, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def _git_log_subjects_for_range(base: str, head: str) -> str:
    # commit subjects (%s)
    p = _run(["git", "log", "--format=%s", f"{base}..{head}"])
    return (p.stdout or "").strip()


def _git_log_body_head() -> str:
    # full message (%B) for HEAD (merge-safe)
    p = _run(["git", "log", "-1", "--format=%B"])
    return (p.stdout or "").strip()


def _extract_token(text: str) -> str:
    # choose highest-severity token that appears in any subject/body line
    found = []
    for line in (text or "").splitlines():
        line = line.strip()
        for t in TOKENS:
            if re.match(rf"^{re.escape(t)}:", line):
                found.append(t)
    if not found:
        return ""
    # max by rank
    return max(found, key=lambda x: TOKEN_RANK[x])


def _load_event_payload() -> dict:
    p = os.getenv("GITHUB_EVENT_PATH", "")
    if not p:
        return {}
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _changed_files_pr(payload: dict) -> list[str]:
    pr = (payload or {}).get("pull_request") or {}
    base = (pr.get("base") or {}).get("sha") or ""
    head = (pr.get("head") or {}).get("sha") or ""
    if not base or not head:
        return []
    p = _run(["git", "diff", "--name-only", base, head])
    out = (p.stdout or "").strip()
    return [x for x in out.splitlines() if x.strip()]


def _changed_files_push(payload: dict) -> list[str]:
    before = (payload or {}).get("before") or ""
    after = (payload or {}).get("after") or os.getenv("GITHUB_SHA", "") or ""
    if before and before != "0000000000000000000000000000000000000000" and after:
        p = _run(["git", "diff", "--name-only", before, after])
        out = (p.stdout or "").strip()
        files = [x for x in out.splitlines() if x.strip()]
        if files:
            return files
    # fallback
    p = _run(["git", "diff", "--name-only", "HEAD~1..HEAD"])
    out = (p.stdout or "").strip()
    return [x for x in out.splitlines() if x.strip()]


@dataclass
class Rule:
    path_regex: str
    min_token: str
    reason: str

    def matches(self, path: str) -> bool:
        return re.search(self.path_regex, path) is not None


def _load_policy(repo_root: Path) -> tuple[dict, list[Rule]]:
    policy_path = repo_root / "docs" / "governance" / "policies" / "DEV_LANGUAGE.yml"
    if not policy_path.exists():
        print(f"ERROR: policy not found: {policy_path}", file=sys.stderr)
        sys.exit(2)

    doc = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
    rules = []
    for r in (doc.get("change_token_policy") or []):
        try:
            rules.append(Rule(
                path_regex=str(r["path_regex"]),
                min_token=str(r["min_token"]),
                reason=str(r.get("reason", "policy rule")),
            ))
        except Exception:
            print("ERROR: invalid rule in DEV_LANGUAGE.yml", file=sys.stderr)
            sys.exit(2)
    return doc, rules


def _required_min_token(changed: Iterable[str], rules: list[Rule]) -> tuple[str, list[str]]:
    # returns (required_token, reasons)
    required = "A-PATCH"
    reasons: list[str] = []

    for f in changed:
        for rule in rules:
            if rule.matches(f):
                req = rule.min_token
                if req not in TOKEN_RANK:
                    print(f"ERROR: unknown token in policy: {req}", file=sys.stderr)
                    sys.exit(2)
                if TOKEN_RANK[req] > TOKEN_RANK[required]:
                    required = req
                reasons.append(f"{rule.reason}: {f} -> min {req}")
    # dedupe reasons (keep order)
    seen = set()
    dedup = []
    for x in reasons:
        if x not in seen:
            seen.add(x)
            dedup.append(x)
    return required, dedup


def main() -> int:
    repo_root = Path(".").resolve()
    event_name = os.getenv("GITHUB_EVENT_NAME", "")
    payload = _load_event_payload()

    # token detection
    if event_name == "pull_request":
        pr = (payload or {}).get("pull_request") or {}
        base = (pr.get("base") or {}).get("sha") or ""
        head = (pr.get("head") or {}).get("sha") or ""
        subjects = _git_log_subjects_for_range(base, head) if base and head else ""
    else:
        subjects = _git_log_body_head()

    token = _extract_token(subjects)

    print("=== verify_change_token ===")
    print(f"event: {event_name or 'unknown'}")
    print("subjects/body:")
    print(subjects if subjects else "(empty)")
    print(f"detected_token: {token or '(none)'}")

    if not token:
        print("FAIL: Missing classification token (A-PATCH/A-MINOR/A-MAJOR).", file=sys.stderr)
        return 1

    # changed files detection
    if event_name == "pull_request":
        changed = _changed_files_pr(payload)
    else:
        changed = _changed_files_push(payload)

    print("changed files:")
    if changed:
        for f in changed:
            print(f"- {f}")
    else:
        print("(none)")

    # policy load + enforce
    _, rules = _load_policy(repo_root)
    required, reasons = _required_min_token(changed, rules)

    print(f"required_min_token: {required}")
    if reasons:
        print("reasons:")
        for r in reasons:
            print(f"- {r}")

    if TOKEN_RANK[token] < TOKEN_RANK[required]:
        print(f"FAIL: token {token} is weaker than required {required}", file=sys.stderr)
        return 1

    print("OK: token satisfies policy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
