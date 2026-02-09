#!/usr/bin/env python3
import argparse, os, re, sys

RULE_POLICY_PARSE_FAIL="STATIC_SCAN_POLICY_PARSE_FAIL"
RULE_WORKFLOW_READ_FAIL="STATIC_SCAN_WORKFLOW_READ_FAIL"
RULE_BROAD_EXCLUDE_FORBIDDEN="STATIC_SCAN_BROAD_EXCLUDE_FORBIDDEN"
RULE_EXCLUDE_NOT_ALLOWLISTED="STATIC_SCAN_EXCLUDE_NOT_ALLOWLISTED"
RULE_FAIL_OPEN_FORBIDDEN="STATIC_SCAN_FAIL_OPEN_FORBIDDEN"

FORBIDDEN=[r'^\*\*$', r'^/$', r'^vendor/\*\*$', r'^third_party/\*\*$']

def eprint(*a): print(*a, file=sys.stderr)
def fail(r,f,d): eprint(f"FAIL {r} file={f} details={d}"); return 1
def ok(m): print(f"OK {m}")

def load_policy(p):
    if not os.path.exists(p):
        return None, "missing_policy"
    try:
        lines = open(p, "r", encoding="utf-8").read().splitlines()
    except Exception as e:
        return None, f"read_error:{e}"
    paths=[]
    for l in lines:
        l=l.strip()
        if l.startswith("- path:"):
            v=l.split(":",1)[1].strip().strip('"\'')
            if v:
                paths.append(v)
    return set(paths), None

def is_scan_workflow(fn, content):
    n = os.path.basename(fn).lower()
    if "scan" in n:
        return True
    c = content.lower()
    return ("codeql" in c) or ("semgrep" in c) or ("sast" in c) or ("gitleaks" in c)

def extract_paths_ignore(content):
    excludes=[]
    lines=content.splitlines()
    for i,l in enumerate(lines):
        if re.match(r'^\s*(paths-ignore|paths_ignore)\s*:\s*$', l):
            base=len(l)-len(l.lstrip(" "))
            j=i+1
            while j < len(lines):
                x=lines[j]
                if not x.strip():
                    j+=1; continue
                ind=len(x)-len(x.lstrip(" "))
                if ind <= base:
                    break
                m=re.match(r'^\s*-\s*(.+?)\s*$', x)
                if m:
                    v=m.group(1).strip().strip('"\'')
                    excludes.append(v)
                j+=1
    return excludes

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--policy", default="policies/static_scan_ignore_allowlist.yaml")
    a=ap.parse_args()

    root=os.path.abspath(a.root)
    allow, err = load_policy(os.path.join(root, a.policy))
    if err:
        return fail(RULE_POLICY_PARSE_FAIL, a.policy, err)

    wfdir=os.path.join(root, ".github/workflows")
    if not os.path.isdir(wfdir):
        ok("no_workflows")
        return 0

    scan_files=[]
    for fn in os.listdir(wfdir):
        if not fn.endswith((".yml",".yaml")):
            continue
        p=os.path.join(wfdir, fn)
        try:
            c=open(p, "r", encoding="utf-8").read()
        except Exception as e:
            return fail(RULE_WORKFLOW_READ_FAIL, f".github/workflows/{fn}", f"read_error:{e}")
        if is_scan_workflow(p, c):
            scan_files.append((fn, c))

    if not scan_files:
        ok("no_scan_workflow_detected")
        return 0

    for fn, c in scan_files:
        if "continue-on-error: true" in c.lower():
            return fail(RULE_FAIL_OPEN_FORBIDDEN, f".github/workflows/{fn}", "continue-on-error:true")

        excludes = extract_paths_ignore(c)
        for ex in excludes:
            for pat in FORBIDDEN:
                if re.match(pat, ex):
                    return fail(RULE_BROAD_EXCLUDE_FORBIDDEN, f".github/workflows/{fn}", f"exclude={ex}")
            if ex not in allow:
                return fail(RULE_EXCLUDE_NOT_ALLOWLISTED, f".github/workflows/{fn}", f"exclude={ex} allowlist={a.policy}")

    ok("static_scan_policy_pass")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
