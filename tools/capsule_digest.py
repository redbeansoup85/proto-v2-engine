import argparse, json, hashlib

def canonical_sha256(obj) -> str:
    b = json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(b).hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--path", default=None,
                    help="optional top-level key to hash only that section")
    args = ap.parse_args()

    data = json.load(open(args.inp, "r", encoding="utf-8"))

    if args.path:
        if args.path not in data:
            raise SystemExit(f"key not found: {args.path}")
        data = data[args.path]

    print(canonical_sha256(data))

if __name__ == "__main__":
    main()
