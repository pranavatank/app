r"""tools/real_ui_tests/rebuild_p5_collect.py — Phase 5 data collector (read-only).

Glob P3_*_*.json results, collect failures, a11y entries, observations, and watchdog issues.
Read PROGRESS.md for per-screen completion and list P4_* logs.
Recompute PersonalData integrity (SHA-256) vs P0_personaldata_hashes.json.
Check git status for data/, backups/ and .db* paths.
Get real DB fingerprint and optionally compare to a baseline or theme_prefs.json bytes.
Write screenshots\rebuild\P5_collected.md with all findings.

No Qt imports; read-only on real DB.
"""
import sys
import os
import json
import hashlib
import sqlite3
import subprocess
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

REBUILD_DIR = Path(__file__).resolve().parent / "screenshots" / "rebuild"
REBUILD_DIR.mkdir(parents=True, exist_ok=True)
BASE = Path(__file__).resolve().parent.parent.parent
REAL_DB = BASE / "data" / "financial.db"
PERSONAL_DATA_DIR = BASE / "data" / "PersonalData"
P0_HASHES_FILE = REBUILD_DIR / "P0_personaldata_hashes.json"
PROGRESS_FILE = REBUILD_DIR / "PROGRESS.md"
FINDINGS_FILE = REBUILD_DIR / "FINDINGS.md"
OUTPUT_FILE = REBUILD_DIR / "P5_collected.md"


def compute_personaldata_sha256():
    """Compute SHA-256 of all files under data\\PersonalData recursively."""
    result = {}
    if not PERSONAL_DATA_DIR.exists():
        return result

    for filepath in sorted(PERSONAL_DATA_DIR.rglob("*")):
        if filepath.is_file():
            try:
                with open(filepath, "rb") as f:
                    sha = hashlib.sha256(f.read()).hexdigest()
                rel_path = filepath.relative_to(BASE)
                result[str(rel_path)] = sha
            except Exception as e:
                print(f"WARNING: cannot hash {filepath}: {e}")

    return result


def load_p0_hashes():
    """Load P0_personaldata_hashes.json."""
    if not P0_HASHES_FILE.exists():
        return {}
    try:
        with open(P0_HASHES_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"WARNING: cannot load P0 hashes: {e}")
        return {}


def compare_personaldata_integrity():
    """Compare current PersonalData hashes with P0 baseline."""
    current = compute_personaldata_sha256()
    baseline = load_p0_hashes()

    added = set(current.keys()) - set(baseline.keys())
    removed = set(baseline.keys()) - set(current.keys())
    changed = []
    for path in set(current.keys()) & set(baseline.keys()):
        if current[path] != baseline[path]:
            changed.append(path)

    return {
        "added": sorted(added),
        "removed": sorted(removed),
        "changed": sorted(changed),
        "matches": len(added) == 0 and len(removed) == 0 and len(changed) == 0,
    }


def fingerprint_real_db():
    """Compute fingerprint of real DB: per-table row count + SHA-256."""
    if not REAL_DB.exists():
        return None

    try:
        conn = sqlite3.connect(f"file:{REAL_DB}?mode=ro", uri=True)
        result = {}

        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()]

        for tbl in tables:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM [{tbl}]").fetchone()[0]
                rows = conn.execute(f"SELECT * FROM [{tbl}] ORDER BY rowid").fetchall()
                sha = hashlib.sha256(repr(rows).encode("utf-8", errors="replace")).hexdigest()
                result[tbl] = {"count": count, "sha256": sha}
            except sqlite3.OperationalError:
                result[tbl] = {"count": 0, "sha256": ""}

        conn.close()
        return result
    except Exception as e:
        print(f"WARNING: cannot fingerprint real DB: {e}")
        return None


def compare_fingerprints(fp_before, fp_after, allowed=()):
    """Compare two fingerprints and return list of changed tables."""
    changed = []
    for table in fp_before.keys():
        if table not in fp_after:
            continue
        if fp_before[table]["count"] != fp_after[table]["count"] or fp_before[table]["sha256"] != fp_after[table]["sha256"]:
            if table not in allowed:
                changed.append(table)
    return changed


def load_p3_results():
    """Glob P3_*_*.json and aggregate results."""
    p3_files = sorted(REBUILD_DIR.glob("P3_*_*.json"))

    all_fails = []
    all_a11y = []
    all_obs = defaultdict(list)
    all_watchdog = []

    for p3_file in p3_files:
        try:
            with open(p3_file, "r") as f:
                data = json.load(f)

            # Collect FAILs
            for result in data.get("results", []):
                if not result.get("ok"):
                    all_fails.append({
                        "file": p3_file.name,
                        "screen": data.get("screen", ""),
                        "env": data.get("env", ""),
                        "name": result.get("name", ""),
                        "detail": result.get("detail", ""),
                    })

            # Collect a11y entries (deduplicate by control)
            seen_controls = set()
            for a11y in data.get("a11y", []):
                control = a11y.get("control", "")
                if control not in seen_controls:
                    all_a11y.append(a11y)
                    seen_controls.add(control)

            # Collect observations (grouped by key)
            for obs in data.get("observations", []):
                key = obs.get("key", "")
                text = obs.get("text", "")
                all_obs[key].append({
                    "file": p3_file.name,
                    "text": text,
                })

            # Collect watchdog failures
            for wd in data.get("watchdog", []):
                all_watchdog.append({
                    "file": p3_file.name,
                    "title": wd.get("title", ""),
                    "detail": str(wd.get("detail", "")),
                })

        except Exception as e:
            print(f"WARNING: cannot load {p3_file}: {e}")

    return {
        "p3_files": [f.name for f in p3_files],
        "fails": all_fails,
        "a11y": all_a11y,
        "observations": dict(all_obs),
        "watchdog": all_watchdog,
    }


def read_progress():
    """Read PROGRESS.md and extract per-screen status."""
    if not PROGRESS_FILE.exists():
        return []

    try:
        with open(PROGRESS_FILE, "r") as f:
            lines = [l.strip() for l in f if l.strip() and l.startswith("-")]
        return lines
    except Exception as e:
        print(f"WARNING: cannot read PROGRESS.md: {e}")
        return []


def list_p4_logs():
    """List P4_*.json and P4_*.log files."""
    json_logs = sorted(REBUILD_DIR.glob("P4_*.json"))
    text_logs = sorted(REBUILD_DIR.glob("P4_*.log"))
    return {
        "json": [f.name for f in json_logs],
        "text": [f.name for f in text_logs],
    }


def check_git_status():
    """Run git status --porcelain and filter for data/, backups/ and .db* paths."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(BASE),
            capture_output=True,
            text=True,
            timeout=10,
        )
        lines = result.stdout.split("\n")
        filtered = []
        for line in lines:
            if any(keyword in line for keyword in ["data/", "backups/", ".db"]):
                filtered.append(line)
        return filtered
    except Exception as e:
        print(f"WARNING: cannot run git status: {e}")
        return []


def read_theme_prefs_bytes():
    """Read theme_prefs.json bytes for optional baseline comparison."""
    theme_file = BASE / "data" / "theme_prefs.json"
    if not theme_file.exists():
        return None
    try:
        with open(theme_file, "rb") as f:
            return f.read()
    except Exception as e:
        print(f"WARNING: cannot read theme_prefs.json: {e}")
        return None


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Phase 5 data collector")
    parser.add_argument("--baseline", type=str, default=None,
                       help="Baseline fingerprint name (compares to FP_<name>.json)")
    parser.add_argument("--prefs-baseline", type=str, default=None,
                       help="Baseline theme_prefs.json bytes (compares to theme_prefs_<name>.json)")
    args = parser.parse_args()

    # Collect all data
    print("Collecting Phase 3 results...")
    p3_data = load_p3_results()

    print("Reading PROGRESS.md...")
    progress = read_progress()

    print("Listing P4 logs...")
    p4_logs = list_p4_logs()

    print("Checking PersonalData integrity...")
    integrity = compare_personaldata_integrity()

    print("Checking git status...")
    git_status = check_git_status()

    print("Fingerprinting real DB...")
    fp_now = fingerprint_real_db()

    print("Reading theme_prefs.json...")
    prefs_bytes = read_theme_prefs_bytes()

    # Build output markdown
    output = []
    output.append("# Phase 5: Collected Data\n")
    output.append(f"**Collected:** {len(p3_data['p3_files'])} P3 result files\n")

    # Summary stats
    output.append("## Summary\n")
    output.append(f"- **P3 test files:** {len(p3_data['p3_files'])}\n")
    output.append(f"- **P3 failures:** {len(p3_data['fails'])}\n")
    output.append(f"- **P3 a11y issues:** {len(p3_data['a11y'])}\n")
    output.append(f"- **P3 observations:** {len(p3_data['observations'])} unique keys\n")
    output.append(f"- **Watchdog events:** {len(p3_data['watchdog'])}\n")
    output.append(f"- **PROGRESS entries:** {len(progress)}\n")
    output.append(f"- **P4 logs:** {len(p4_logs['json'])} JSON, {len(p4_logs['text'])} text\n")

    # P3 Failures
    output.append("\n## Phase 3 Failures\n")
    if p3_data['fails']:
        output.append("| File | Screen | Env | Name | Detail |\n")
        output.append("|------|--------|-----|------|--------|\n")
        for fail in p3_data['fails']:
            output.append(f"| {fail['file']} | {fail['screen']} | {fail['env']} | {fail['name']} | {fail['detail'][:50]} |\n")
    else:
        output.append("*(no failures)*\n")

    # P3 Accessibility
    output.append("\n## Accessibility Issues (P3)\n")
    if p3_data['a11y']:
        output.append("| Control | Located By |\n")
        output.append("|---------|------------|\n")
        for item in p3_data['a11y']:
            output.append(f"| {item.get('control', '')} | {item.get('located_by', '')} |\n")
    else:
        output.append("*(no a11y issues recorded)*\n")

    # P3 Observations
    output.append("\n## Observations (P3)\n")
    if p3_data['observations']:
        for key in sorted(p3_data['observations'].keys()):
            output.append(f"\n### {key}\n")
            for obs in p3_data['observations'][key]:
                output.append(f"- {obs['text']} ({obs['file']})\n")
    else:
        output.append("*(no observations)*\n")

    # Watchdog Events
    output.append("\n## Watchdog Events (P3)\n")
    if p3_data['watchdog']:
        output.append("| File | Title | Detail |\n")
        output.append("|------|-------|--------|\n")
        for wd in p3_data['watchdog']:
            output.append(f"| {wd['file']} | {wd['title']} | {wd['detail'][:40]} |\n")
    else:
        output.append("*(no watchdog events)*\n")

    # PROGRESS
    output.append("\n## Progress Entries\n")
    if progress:
        for entry in progress:
            output.append(f"- {entry}\n")
    else:
        output.append("*(no progress entries)*\n")

    # P4 Logs
    output.append("\n## Phase 4 Logs\n")
    output.append("### JSON Results\n")
    if p4_logs['json']:
        for log in p4_logs['json']:
            output.append(f"- {log}\n")
    else:
        output.append("*(no P4 JSON logs)*\n")

    output.append("\n### Text Logs\n")
    if p4_logs['text']:
        for log in p4_logs['text']:
            output.append(f"- {log}\n")
    else:
        output.append("*(no P4 text logs)*\n")

    # Integrity Checks
    output.append("\n## Integrity Checks\n")

    output.append("\n### PersonalData Hashes\n")
    output.append(f"- **Matches P0:** {integrity['matches']}\n")
    if integrity['added']:
        output.append(f"- **Added:** {', '.join(integrity['added'][:3])}")
        if len(integrity['added']) > 3:
            output.append(f" (and {len(integrity['added']) - 3} more)")
        output.append("\n")
    if integrity['removed']:
        output.append(f"- **Removed:** {', '.join(integrity['removed'][:3])}")
        if len(integrity['removed']) > 3:
            output.append(f" (and {len(integrity['removed']) - 3} more)")
        output.append("\n")
    if integrity['changed']:
        output.append(f"- **Changed:** {', '.join(integrity['changed'][:3])}")
        if len(integrity['changed']) > 3:
            output.append(f" (and {len(integrity['changed']) - 3} more)")
        output.append("\n")

    output.append("\n### Git Status (data/, backups/, .db*)\n")
    if git_status:
        for line in git_status:
            output.append(f"- {line}\n")
    else:
        output.append("*(clean)*\n")

    output.append("\n### Real DB Fingerprint\n")
    if fp_now:
        output.append(f"- **Tables:** {len(fp_now)}\n")
        total_rows = sum(t.get("count", 0) for t in fp_now.values())
        output.append(f"- **Total rows:** {total_rows}\n")
        output.append(f"- **Status:** captured (use --baseline to compare)\n")

        if args.baseline:
            baseline_file = REBUILD_DIR / f"FP_{args.baseline}.json"
            if baseline_file.exists():
                try:
                    with open(baseline_file, "r") as f:
                        fp_baseline = json.load(f)
                    changed = []
                    for table in fp_baseline.keys():
                        if table not in fp_now:
                            continue
                        if fp_baseline[table]["count"] != fp_now[table]["count"]:
                            changed.append(f"{table} ({fp_baseline[table]['count']} → {fp_now[table]['count']})")

                    if changed:
                        output.append(f"- **Changed tables (vs {args.baseline}):**\n")
                        for change in changed:
                            output.append(f"  - {change}\n")
                    else:
                        output.append(f"- **No changes vs {args.baseline}**\n")
                except Exception as e:
                    output.append(f"- **Baseline comparison failed:** {e}\n")
            else:
                output.append(f"- **Baseline not found:** FP_{args.baseline}.json\n")
    else:
        output.append("- **Status:** failed to fingerprint (DB may not exist)\n")

    output.append("\n### Theme Prefs\n")
    if prefs_bytes:
        output.append(f"- **Bytes:** {len(prefs_bytes)}\n")
        output.append(f"- **Status:** captured (use --prefs-baseline to compare)\n")

        if args.prefs_baseline:
            baseline_file = REBUILD_DIR / f"theme_prefs_{args.prefs_baseline}.json"
            if baseline_file.exists():
                try:
                    with open(baseline_file, "rb") as f:
                        baseline_bytes = f.read()
                    if prefs_bytes == baseline_bytes:
                        output.append(f"- **Match:** yes (vs {args.prefs_baseline})\n")
                    else:
                        output.append(f"- **Match:** no (vs {args.prefs_baseline})\n")
                        output.append(f"  - Baseline: {len(baseline_bytes)} bytes\n")
                        output.append(f"  - Current: {len(prefs_bytes)} bytes\n")
                except Exception as e:
                    output.append(f"- **Baseline comparison failed:** {e}\n")
            else:
                output.append(f"- **Baseline not found:** theme_prefs_{args.prefs_baseline}.json\n")
    else:
        output.append("- **Status:** file not found\n")

    output.append("\n---\n")
    output.append("*End of P5 collected data.*\n")

    # Write output
    with open(OUTPUT_FILE, "w") as f:
        f.write("".join(output))

    print(f"\nOutput written to {OUTPUT_FILE}")
    print(f"File size: {OUTPUT_FILE.stat().st_size} bytes")

    return 0


if __name__ == "__main__":
    sys.exit(main())
