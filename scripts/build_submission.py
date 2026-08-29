#!/usr/bin/env python3
"""Build and verify the multi-file Kaggle submission archive."""

from __future__ import annotations

import argparse
import compileall
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "submission.tar.gz")
    args = parser.parse_args()
    if not compileall.compile_dir(ROOT / "src", quiet=1) or not compileall.compile_file(ROOT / "main.py", quiet=1):
        raise SystemExit("Python compilation failed")
    with tarfile.open(args.output, "w:gz") as archive:
        archive.add(ROOT / "main.py", arcname="main.py")
        for path in sorted((ROOT / "src").rglob("*.py")):
            archive.add(path, arcname=str(path.relative_to(ROOT)))
    with tarfile.open(args.output, "r:gz") as archive:
        names = set(archive.getnames())
        if "main.py" not in names or "src/kaggriculture_agent/policy.py" not in names:
            raise SystemExit("submission archive is incomplete")
    print(args.output)


if __name__ == "__main__":
    main()
