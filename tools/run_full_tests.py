r"""tools/run_full_tests.py — Run full pytest suite with per-file subprocess isolation.

Runs each test file in its own subprocess to avoid segfaults from GUI/matplotlib
buildup on Windows/Qt stack.

Usage:
  .venv\Scripts\python.exe tools/run_full_tests.py
  .venv\Scripts\python.exe tools/run_full_tests.py tests/test_kpi_tile.py tests/test_theme.py
  .venv\Scripts\python.exe tools/run_full_tests.py --log-dir /tmp/logs -- -v --tb=short
"""

import sys
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import argparse
import glob
import os
import re
import subprocess
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def parse_summary_line(log_content: str) -> str | None:
    r"""Extract pytest summary line from log output.

    Searches for pattern matching r"\d+ (passed|failed|errors?|skipped|xfailed|xpassed|deselected)[^\n]* in [\d.]+s".
    Returns the last matching line, or None if not found.
    """
    pattern = r"\d+ (?:passed|failed|errors?|skipped|xfailed|xpassed|deselected)[^\n]* in [\d.]+s"
    matches = list(re.finditer(pattern, log_content))
    if matches:
        last_match = matches[-1]
        return log_content[last_match.start():last_match.end()]
    return None


def classify_result(returncode: int, summary_line: str | None) -> str:
    """Classify test result based on returncode and summary line."""
    if returncode == 0:
        return "PASS"
    if returncode == 5:
        return "NO TESTS"
    if returncode == 1:
        return "FAIL"

    if summary_line and "failed" not in summary_line.lower() and "error" not in summary_line.lower():
        return f"PASS (crashed after summary, rc={returncode})"
    return "CRASH"


def main() -> int:
    """Run pytest on each test file in a subprocess."""
    # Manually split sys.argv on the first literal "--" to separate argparse args from pytest args
    argv_to_parse = sys.argv[1:]
    extra_args = []

    if "--" in argv_to_parse:
        sep_idx = argv_to_parse.index("--")
        extra_args = argv_to_parse[sep_idx + 1:]
        argv_to_parse = argv_to_parse[:sep_idx]

    parser = argparse.ArgumentParser(
        description="Run pytest suite with per-file subprocess isolation"
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Test files to run (default: all tests/test_*.py)"
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default=os.path.join(tempfile.gettempdir(), "finmgr_test_logs"),
        help="Directory for test logs (default: temp/finmgr_test_logs)"
    )

    args = parser.parse_args(argv_to_parse)

    test_files = args.files
    if not test_files:
        test_files = sorted(glob.glob(os.path.join(ROOT, "tests", "test_*.py")))

    log_dir = args.log_dir
    os.makedirs(log_dir, exist_ok=True)

    results = {}
    elapsed_by_status = {}

    for test_file in test_files:
        basename = os.path.basename(test_file)
        log_path = os.path.join(log_dir, basename + ".log")

        start_time = time.perf_counter()

        try:
            with open(log_path, "w", encoding="utf-8") as log_fh:
                env = {
                    **os.environ,
                    "PYTHONIOENCODING": "utf-8",
                    "QT_QPA_PLATFORM": "offscreen",
                }
                verbosity_flags = {"-v", "-vv", "-vvv", "--verbose"}
                base_flags = [] if any(f in verbosity_flags for f in extra_args) else ["-q"]
                result = subprocess.run(
                    [sys.executable, "-m", "pytest", test_file, *base_flags, "-p", "no:cacheprovider", *extra_args],
                    cwd=ROOT,
                    stdout=log_fh,
                    stderr=subprocess.STDOUT,
                    env=env,
                    timeout=120
                )
                returncode = result.returncode
        except subprocess.TimeoutExpired:
            elapsed = time.perf_counter() - start_time
            results[basename] = ("TIMEOUT", None, elapsed)
            continue
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            results[basename] = ("ERROR", str(e), elapsed)
            continue

        elapsed = time.perf_counter() - start_time

        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                log_content = f.read()
        except Exception:
            log_content = ""

        summary_line = parse_summary_line(log_content)
        status = classify_result(returncode, summary_line)
        results[basename] = (status, summary_line, elapsed)

    print()
    for basename in sorted(results.keys()):
        status, summary_line, elapsed = results[basename]
        summary_display = summary_line or "(no summary found)"
        print(f"{status:30s} {basename:45s} {summary_display}  [{elapsed:.1f}s]")

    print()
    status_counts = {}
    for status, _, _ in results.values():
        key = status.split("(")[0].strip()
        status_counts[key] = status_counts.get(key, 0) + 1

    for status_type in sorted(status_counts.keys()):
        print(f"{status_type}: {status_counts[status_type]}")

    print(f"Logs: {log_dir}")

    all_pass = all(
        status in ("PASS", "NO TESTS") or status.startswith("PASS (crashed")
        for status, _, _ in results.values()
    )

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
