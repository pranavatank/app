#!/usr/bin/env python3
"""Read-only current-tree privacy gate for tracked files.

The report deliberately contains only file paths and match counts. Secret
values and matching lines are never emitted.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SECRET_FILE = ROOT / "data" / "data" / "Pranav" / "password.txt"
FORBIDDEN_PATH_PARTS = (
    "data/data/",
    "data/personaldata/",
    "data/financial.db",
    "data/financial.sqlite",
    "data/financial.sqlite3",
)


def read_secret(path: Path) -> list[bytes]:
    """Read credential lines; errors and empty files must fail the opted-in gate."""
    lines = path.read_text(encoding="utf-8").splitlines()
    values: list[bytes] = []
    for line in lines:
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        # Support simple `label: value` / `label=value` local password files.
        separators = [index for index in (value.find(":"), value.find("=")) if index >= 0]
        if separators:
            value = value[min(separators) + 1:].strip()
        if value:
            values.append(value.encode("utf-8"))
    if not values:
        raise ValueError("credential file is empty")
    return values


def tracked_paths(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={root}", "ls-files", "-z"],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
    )
    return [root / item.decode("utf-8", "surrogateescape")
            for item in result.stdout.split(b"\0") if item]


def private_path(path: Path, root: Path) -> bool:
    try:
        lexical_rel = path.relative_to(root).as_posix().lower()
        if any(part in lexical_rel for part in FORBIDDEN_PATH_PARTS):
            return True
        resolved_root = root.resolve()
        resolved_path = path.resolve()
        rel = resolved_path.relative_to(resolved_root).as_posix().lower()
    except (ValueError, OSError, RuntimeError):
        return False
    return any(part in rel for part in FORBIDDEN_PATH_PARTS)


def audit(root: Path, secrets: list[bytes], paths: list[Path] | None = None) -> tuple[list[tuple[str, int]], list[str], list[str]]:
    paths = tracked_paths(root) if paths is None else paths
    secret_hits: list[tuple[str, int]] = []
    private_hits: list[str] = []
    read_failures: list[str] = []
    for path in paths:
        rel = path.relative_to(root).as_posix()
        if private_path(path, root):
            private_hits.append(rel)
        try:
            blob = path.read_bytes()
        except OSError:
            read_failures.append(rel)
            continue
        count = sum(blob.count(secret) for secret in secrets if secret)
        if count:
            secret_hits.append((rel, count))
    return secret_hits, private_hits, read_failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-local-secrets", action="store_true",
                        help="explicitly read the ignored local password file and scan tracked files")
    args = parser.parse_args(argv)
    if args.check_local_secrets:
        try:
            secrets = read_secret(DEFAULT_SECRET_FILE)
        except (OSError, UnicodeError, ValueError):
            print(f"local credentials unavailable or empty: {DEFAULT_SECRET_FILE.relative_to(ROOT).as_posix()}")
            return 1
    else:
        secrets = []
    secret_hits, private_hits, read_failures = audit(ROOT, secrets)
    for path, count in secret_hits:
        print(f"secret match: {path} ({count})")
    for path in private_hits:
        print(f"forbidden private path: {path}")
    for path in read_failures:
        print(f"tracked file unreadable: {path}")
    failed = bool(secret_hits or private_hits or read_failures)
    if not args.check_local_secrets and not failed:
        print("tracked-path check passed; local secrets not checked")
    elif not failed:
        print("privacy audit passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
