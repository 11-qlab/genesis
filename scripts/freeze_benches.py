#!/usr/bin/env python3
"""
Freeze the family benches by writing a MANIFEST.json with sha256 of every
seed and test file, plus a manifest hash. Commit MANIFEST.json to git
BEFORE running the distribution test.

This is the commitment: if the manifest is public before the test runs,
nobody can accuse you of tuning on the test set after the fact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--families-dir", default="bench/families")
    ap.add_argument("--out", default="bench/families/MANIFEST.json")
    args = ap.parse_args()

    os_cwd = ROOT
    fam_dir = (os_cwd / args.families_dir).resolve()

    files = sorted(fam_dir.rglob("*.jsonl"))
    entries = []
    for f in files:
        entries.append({
            "path": str(f.relative_to(os_cwd)),
            "sha256": sha256_file(f),
            "size": f.stat().st_size,
        })

    manifest = {
        "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "files": entries,
    }
    body = json.dumps(manifest, sort_keys=True)
    manifest["manifest_sha256"] = hashlib.sha256(body.encode()).hexdigest()

    out = (os_cwd / args.out).resolve()
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2))

    print(f"froze {len(files)} files")
    print(f"manifest: {out}")
    print(f"MANIFEST_SHA256: {manifest['manifest_sha256']}")
    print(f"\nnow: git add {args.out} && git commit -m 'freeze families' && git push")


if __name__ == "__main__":
    main()
