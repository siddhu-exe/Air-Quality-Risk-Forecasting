"""Download the large, regenerable datasets from the GitHub Release named in data/MANIFEST.json and verify their SHA-256.

    python scripts/fetch_data.py            # fetch missing or corrupt files
    python scripts/fetch_data.py --check    # verify only, never download

Files that already exist with the right hash are left alone. Standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "data" / "MANIFEST.json"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="verify existing files only")
    args = parser.parse_args()

    manifest = json.loads(MANIFEST.read_text())
    failures = 0
    for rel, info in manifest["files"].items():
        target = REPO_ROOT / rel
        if target.exists() and sha256_of(target) == info["sha256"]:
            print(f"ok        {rel}")
            continue
        if args.check:
            print(f"MISSING/BAD {rel}")
            failures += 1
            continue
        url = manifest["base_url"] + info["asset"]
        print(f"download  {rel}  <- {url}")
        target.parent.mkdir(parents=True, exist_ok=True)
        part = target.with_suffix(target.suffix + ".part")
        try:
            urllib.request.urlretrieve(url, part)  # noqa: S310 - fixed https URL from the manifest
        except OSError as err:
            print(f"FAILED    {rel}: {err}", file=sys.stderr)
            failures += 1
            continue
        if sha256_of(part) != info["sha256"]:
            part.unlink()
            print(f"HASH MISMATCH {rel}; file discarded", file=sys.stderr)
            failures += 1
            continue
        part.replace(target)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
