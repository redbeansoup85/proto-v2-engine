#!/usr/bin/env python3
from __future__ import annotations
import argparse, os, re, subprocess, sys
from dataclasses import dataclass

RULE_SUBMODULE_PRESENT_BUT_NOT_ALLOWED = "SUBMODULE_PRESENT_BUT_NOT_ALLOWED"
RULE_SUBMODULE_URL_MISMATCH = "SUBMODULE_URL_MISMATCH"
RULE_SUBMODULE_PIN_MISMATCH = "SUBMODULE_PIN_MISMATCH"
RULE_GITMODULES_PARSE_FAIL = "GITMODULES_PARSE_FAIL"
RULE_ALLOWLIST_PARSE_FAIL = "ALLOWLIST_PARSE_FAIL"
RULE_GIT_CMD_FAIL = "GIT_CMD_FAIL"

ALLOWLIST_DEFAULT = "policies/submodules_allowlist.yaml"

@dataclass(frozen=True)
class AllowEntry:
    path: str
    url: str
    pinned_commit: str

def eprint(*a): print(*a, file=sys.stderr)
def fail(rule, file, details): eprint(f"FAIL {rule} file={file} details={details}"); return 1
def ok(msg): print(f"OK {msg}")

def run_git(root, args):
    p = subprocess.run(["git"] + args, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return p.returncode, p.stdout, p.stderr

def load_allowlist_yaml(path):
    if not os.path.exists(path):
        return None, f"missing:{path}"
    try:
        lines = open(path, "r", encoding="utf-8").read().splitlines()
    except Exception as e:
        return None, f"read_error:{e}"

    entries = []
    cur = None
    in_entries = False

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line == "entries:":
            in_entries = True
            continue
        if not in_entries:
            continue

        if line == "-":
            if cur:
                entries.append(cur)
            cur = {}
            continue

        if line.startswith("- "):
            if cur:
                entries.append(cur)
            cur = {}
            kv = line[2:]
            if ":" not in kv:
                return None, "invalid_inline_entry"
            k, v = kv.split(":", 1)
            cur[k.strip()] = v.strip().strip('"\'')
            continue

        if ":" in line and cur is not None:
            k, v = line.split(":", 1)
            cur[k.strip()] = v.strip().strip('"\'')
            continue

    if cur:
        entries.append(cur)

    allow = {}
    for d in entries:
        if not d:
            continue
        if not all(k in d for k in ("path", "url", "pinned_commit")):
            return None, "invalid_entry_missing_keys"
        allow[d["path"]] = AllowEntry(d["path"], d["url"], d["pinned_commit"])
    return allow, None

def parse_gitmodules(p):
    try:
        lines = open(p, "r", encoding="utf-8").read().splitlines()
    except Exception as e:
        return None, f"read_error:{e}"
    subs, cur = {}, None
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r'\[submodule "([^"]+)"\]', line)
        if m:
            if cur and "path" in cur:
                subs[cur["path"]] = cur
            cur = {"name": m.group(1)}
            continue
        if "=" in line and cur is not None:
            k, v = [x.strip() for x in line.split("=", 1)]
            cur[k] = v
    if cur and "path" in cur:
        subs[cur["path"]] = cur
    return subs, None

def get_status(root):
    rc, out, err = run_git(root, ["submodule", "status", "--recursive"])
    if rc != 0:
        return None, (err.strip() or out.strip() or "git_submodule_status_failed")
    status = {}
    for raw in out.splitlines():
        if not raw.strip():
            continue
        parts = raw.strip().split()
        if len(parts) < 2:
            return None, f"unparseable_line:{raw.strip()}"
        sha = parts[0].lstrip("+-")
        path = parts[1]
        status[path] = sha
    return status, None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--allowlist", default=ALLOWLIST_DEFAULT)
    a = ap.parse_args()

    root = os.path.abspath(a.root)
    allow, err = load_allowlist_yaml(os.path.join(root, a.allowlist))
    if err:
        return fail(RULE_ALLOWLIST_PARSE_FAIL, a.allowlist, err)

    gm = os.path.join(root, ".gitmodules")
    has_gm = os.path.exists(gm)

    rc, out, err2 = run_git(root, ["submodule", "status", "--recursive"])
    has_status = (rc == 0 and out.strip() != "")

    if not has_gm and not has_status:
        ok("no_submodules")
        return 0

    subs = {}
    if has_gm:
        subs, perr = parse_gitmodules(gm)
        if perr:
            return fail(RULE_GITMODULES_PARSE_FAIL, ".gitmodules", perr)

    status, serr = get_status(root)
    if serr:
        return fail(RULE_GIT_CMD_FAIL, ".gitmodules" if has_gm else ".", serr)

    all_paths = set(subs.keys()) | set(status.keys())

    for path in sorted(all_paths):
        if path not in allow:
            return fail(RULE_SUBMODULE_PRESENT_BUT_NOT_ALLOWED, ".gitmodules" if has_gm else ".", f"path={path}")

        entry = allow[path]

        actual_url = subs.get(path, {}).get("url", "")
        if actual_url and actual_url != entry.url:
            return fail(RULE_SUBMODULE_URL_MISMATCH, ".gitmodules", f"path={path} expected={entry.url} actual={actual_url}")

        actual_sha = status.get(path, "")
        if actual_sha and actual_sha != entry.pinned_commit:
            return fail(RULE_SUBMODULE_PIN_MISMATCH, ".gitmodules", f"path={path} expected={entry.pinned_commit} actual={actual_sha}")

    ok("submodule_hygiene_pass")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
