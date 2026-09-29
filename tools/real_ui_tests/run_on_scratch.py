r"""tools/real_ui_tests/run_on_scratch.py — Run a rebuild script in scratch-DB mode.

Usage: python run_on_scratch.py [--fresh] <script> [args...]

Scratch DB = BASE/"backups"/"phase3_scratch.db"
Scratch theme prefs = tools/real_ui_tests/screenshots/rebuild/scratch_theme_prefs.json

If --fresh or scratch DB is missing: copy the real DB (verified by integrity_check
and per-table counts), copy real theme_prefs.json bytes if present.

Patches config.DB_PATH, core.database.DB_PATH, core.backup_manager.DB_PATH to
the scratch DB, and core.session._CONFIG_FILE / ui.theme.theme_manager._CONFIG_FILE
to the scratch prefs, BEFORE importing any app module.

Runs the script and verifies the real DB/theme_prefs were not modified.
"""
import os
import sys
import hashlib
import runpy
import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE))

from tools.real_ui_tests.rebuild_common import (
    REAL_DB_PATH, BACKUPS, RUIH_DIR, fingerprint_real_db, diff_fingerprints,
    read_theme_prefs,
)

SCRATCH_DB = BACKUPS / "phase3_scratch.db"
SCRATCH_THEME_PREFS = RUIH_DIR / "scratch_theme_prefs.json"
REAL_THEME_PREFS = BASE / "data" / "theme_prefs.json"


def copy_db_with_sqlite_backup_api(src_path, dest_path):
    src_conn = sqlite3.connect(f"file:{src_path}?mode=ro", uri=True)
    dest_conn = sqlite3.connect(str(dest_path))
    with dest_conn:
        src_conn.backup(dest_conn)
    src_conn.close()
    dest_conn.close()


def verify_db_integrity_and_counts(db_path, src_db_path):
    check_conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    integrity = check_conn.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        check_conn.close()
        raise RuntimeError(f"DB integrity check failed: {integrity}")

    src_conn = sqlite3.connect(f"file:{src_db_path}?mode=ro", uri=True)
    tables = [r[0] for r in src_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()]

    for t in tables:
        src_count = src_conn.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
        dest_count = check_conn.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
        if src_count != dest_count:
            src_conn.close()
            check_conn.close()
            raise RuntimeError(f"table {t} count mismatch: src={src_count} dest={dest_count}")

    src_conn.close()
    check_conn.close()


def main():
    fresh = False
    script = None
    script_args = []

    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--fresh":
            fresh = True
        else:
            script = arg
            script_args = sys.argv[i+2:]
            break

    if script is None:
        print("Usage: python run_on_scratch.py [--fresh] <script> [args...]")
        sys.exit(1)

    if "--real" in script_args:
        print("STOP: --real not allowed in target script args")
        sys.exit(1)

    script_path = Path(script).resolve()
    if not script_path.exists():
        print(f"Script not found: {script_path}")
        sys.exit(1)

    BACKUPS.mkdir(parents=True, exist_ok=True)
    RUIH_DIR.mkdir(parents=True, exist_ok=True)

    if fresh or not SCRATCH_DB.exists():
        copy_db_with_sqlite_backup_api(REAL_DB_PATH, SCRATCH_DB)
        verify_db_integrity_and_counts(SCRATCH_DB, REAL_DB_PATH)
        print(f"Scratch DB copied and verified: {SCRATCH_DB}")

        real_theme_bytes = read_theme_prefs()
        if real_theme_bytes:
            SCRATCH_THEME_PREFS.write_bytes(real_theme_bytes)
            print(f"Scratch theme prefs copied: {SCRATCH_THEME_PREFS}")

    fp_before_db = fingerprint_real_db(REAL_DB_PATH)
    fp_before_theme = None
    if REAL_THEME_PREFS.exists():
        fp_before_theme = hashlib.sha256(REAL_THEME_PREFS.read_bytes()).hexdigest()

    import config
    import core.database
    import core.backup_manager
    import core.session
    import ui.theme.theme_manager as tm

    config.DB_PATH = str(SCRATCH_DB)
    core.database.DB_PATH = str(SCRATCH_DB)
    core.backup_manager.DB_PATH = str(SCRATCH_DB)

    core.session._CONFIG_DIR = str(SCRATCH_THEME_PREFS.parent)
    core.session._CONFIG_FILE = str(SCRATCH_THEME_PREFS)
    tm._CONFIG_DIR = str(SCRATCH_THEME_PREFS.parent)
    tm._CONFIG_FILE = str(SCRATCH_THEME_PREFS)

    resolved_db = Path(config.DB_PATH).resolve()
    assert resolved_db != REAL_DB_PATH.resolve(), f"DB patch failed: {resolved_db} == {REAL_DB_PATH.resolve()}"
    print(f"Config patched to scratch DB: {config.DB_PATH}")

    exit_code = 0
    exception_to_raise = None
    try:
        sys.argv = [str(script_path)] + script_args
        runpy.run_path(str(script_path), run_name="__main__")
    except SystemExit as e:
        exit_code = e.code if isinstance(e.code, int) else (1 if e.code else 0)
    except Exception as e:
        exception_to_raise = e
    finally:
        fp_after_db = fingerprint_real_db(REAL_DB_PATH)
        fp_after_theme = None
        if REAL_THEME_PREFS.exists():
            fp_after_theme = hashlib.sha256(REAL_THEME_PREFS.read_bytes()).hexdigest()

        changed_tables = diff_fingerprints(fp_before_db, fp_after_db)
        if changed_tables:
            print(f"STOP: real DB changed: {changed_tables}")
            sys.exit(3)

        if fp_before_theme != fp_after_theme:
            print(f"STOP: real theme_prefs.json changed")
            sys.exit(3)

        if exception_to_raise:
            raise exception_to_raise

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
