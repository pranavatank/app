"""Run pytest files in isolated subprocesses, optionally by feature."""
import sys
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "tests" / "feature_manifest.json"


def parse_summary_line(log_content: str) -> str | None:
    pattern = r"\d+ (?:passed|failed|errors?|skipped|xfailed|xpassed|deselected)[^\n]* in [\d.]+s"
    matches = list(re.finditer(pattern, log_content))
    return log_content[matches[-1].start():matches[-1].end()] if matches else None


def classify_result(returncode: int, summary_line: str | None) -> str:
    if returncode == 0:
        return "PASS"
    if returncode == 5:
        return "NO TESTS"
    if returncode == 1:
        return "FAIL"
    return "CRASH"


def load_manifest(path=MANIFEST):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("version") != 1 or not isinstance(data.get("features"), dict):
        raise ValueError("Unsupported test feature manifest")
    return data


def discover_tests(inputs=(), features=(), manifest=None):
    """Resolve explicit files/directories and feature names to ordered test paths."""
    manifest = manifest or load_manifest()
    available = manifest["features"]
    unknown = sorted(set(features) - set(available))
    if unknown:
        raise ValueError("Unknown feature(s): " + ", ".join(unknown))
    candidates = []
    for feature in features:
        candidates.extend(available[feature])
    for item in inputs:
        path = Path(item)
        if not path.is_absolute():
            path = ROOT / path
        if path.is_dir():
            found = sorted(
                p.relative_to(ROOT).as_posix()
                for p in path.rglob("test_*.py")
                if not _is_native_or_support_test(p)
            )
            if not found:
                raise ValueError(f"Directory contains no test_*.py files: {item}")
            candidates.extend(found)
        else:
            if _is_native_or_support_test(path):
                raise ValueError("Native UI and support scripts are not headless test targets")
            candidates.append(path.relative_to(ROOT).as_posix() if path.is_absolute() and path.is_relative_to(ROOT) else str(item).replace("\\", "/"))
    if not inputs and not features:
        candidates.extend(
            p.relative_to(ROOT).as_posix()
            for p in (ROOT / "tests").rglob("test_*.py")
            if not _is_native_or_support_test(p)
        )
    if not candidates:
        raise ValueError("No tests selected. Choose a non-empty feature, test directory, or test file.")
    # Manifest entries and discovered paths must stay within the repository.
    resolved = []
    seen = set()
    for item in candidates:
        path = (ROOT / item).resolve()
        if not path.is_relative_to(ROOT):
            raise ValueError(f"Test path escapes repository: {item}")
        if _is_native_or_support_test(path):
            raise ValueError(
                f"Native UI and support scripts are not headless test targets: {item}"
            )
        rel = path.relative_to(ROOT).as_posix()
        if rel not in seen:
            seen.add(rel)
            resolved.append((rel, str(path)))
    return sorted(resolved)


def _is_native_or_support_test(path):
    resolved = Path(path).resolve()
    return any(
        resolved.is_relative_to(ROOT / "tests" / folder)
        for folder in ("native", "support")
    )


def _log_name(relative_path):
    return relative_path.replace("/", "__") + ".log"


def main() -> int:
    argv = sys.argv[1:]
    extra_args = []
    if "--" in argv:
        split = argv.index("--")
        extra_args, argv = argv[split + 1:], argv[:split]
    parser = argparse.ArgumentParser(description="Run pytest files with per-file subprocess isolation")
    parser.add_argument("paths", nargs="*", help="Test files or directories (default: all tests recursively)")
    parser.add_argument("--feature", action="append", default=[], help="Feature from tests/feature_manifest.json; repeatable")
    parser.add_argument("--list", action="store_true", help="List selected test paths without running them")
    parser.add_argument("--log-dir", help="Log directory (default: artifacts/pytest/<UTC timestamp>)")
    args = parser.parse_args(argv)
    if args.log_dir is None:
        run_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        args.log_dir = str(ROOT / "artifacts" / "pytest" / run_stamp)
    try:
        test_files = discover_tests(args.paths, args.feature)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    if args.list:
        for relative, _ in test_files:
            print(relative)
        return 0

    os.makedirs(args.log_dir, exist_ok=True)
    results = {}
    for relative, path in test_files:
        log_path = os.path.join(args.log_dir, _log_name(relative))
        started = time.perf_counter()
        print(f"Running {relative}...", flush=True)
        try:
            with open(log_path, "w", encoding="utf-8") as log_fh:
                env = {**os.environ, "PYTHONIOENCODING": "utf-8", "QT_QPA_PLATFORM": "offscreen"}
                verbosity = {"-v", "-vv", "-vvv", "--verbose"}
                base = [] if any(flag in verbosity for flag in extra_args) else ["-q"]
                proc = subprocess.run([sys.executable, "-m", "pytest", path, *base, "-p", "no:cacheprovider", *extra_args], cwd=ROOT, stdout=log_fh, stderr=subprocess.STDOUT, env=env, timeout=120)
                code = proc.returncode
                log_fh.write(f"\n[run_full_tests] process exit code: {code}\n")
            content = Path(log_path).read_text(encoding="utf-8", errors="replace")
            summary = parse_summary_line(content)
            status = classify_result(code, summary)
            details = summary
        except subprocess.TimeoutExpired:
            status, details = "TIMEOUT", None
        except Exception as exc:
            status, details = "ERROR", str(exc)
        results[relative] = (status, details, time.perf_counter() - started)

    print()
    for relative in sorted(results):
        status, summary, elapsed = results[relative]
        print(f"{status:12s} {relative:55s} {summary or '(no summary found)'} [{elapsed:.1f}s]")
    print()
    counts = {}
    for status, _, _ in results.values():
        counts[status] = counts.get(status, 0) + 1
    for status in sorted(counts):
        print(f"{status}: {counts[status]}")
    print(f"Logs: {args.log_dir}")
    return 0 if all(status in ("PASS", "NO TESTS") for status, _, _ in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
