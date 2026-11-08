"""Restore must validate a backup before changing the destination."""

import sqlite3
import pytest

import core.database as database


@pytest.fixture
def target_db(tmp_path, monkeypatch):
    target = tmp_path / "live.sqlite"
    monkeypatch.setattr(database, "DB_PATH", str(target))
    monkeypatch.setattr(database, "DATA_DIR", str(tmp_path))
    database.initialise_database()
    conn = database.get_connection()
    conn.execute("INSERT INTO Person (full_name) VALUES (?)", ("destination sentinel",))
    conn.commit()
    conn.close()
    return target


def _create_app_db(path, person_name):
    old_db_path, old_data_dir = database.DB_PATH, database.DATA_DIR
    try:
        database.DB_PATH = str(path)
        database.DATA_DIR = str(path.parent)
        database.initialise_database()
        conn = database.get_connection()
        conn.execute("INSERT INTO Person (full_name) VALUES (?)", (person_name,))
        conn.commit()
        conn.close()
    finally:
        database.DB_PATH, database.DATA_DIR = old_db_path, old_data_dir


def _people(path):
    conn = sqlite3.connect(path)
    try:
        return [r[0] for r in conn.execute("SELECT full_name FROM Person ORDER BY person_id")]
    finally:
        conn.close()


def _insert_deposit_transaction(path, description):
    old_db_path, old_data_dir = database.DB_PATH, database.DATA_DIR
    try:
        database.DB_PATH = str(path)
        database.DATA_DIR = str(path.parent)
        conn = database.get_connection()
        person_id = conn.execute(
            "INSERT INTO Person (full_name) VALUES (?)", ("backfill fixture",)
        ).lastrowid
        account_id = conn.execute(
            "INSERT INTO BankAccount (person_id, bank_name, account_type) VALUES (?, ?, ?)",
            (person_id, "Backfill fixture bank", "Savings"),
        ).lastrowid
        transaction_id = conn.execute(
            "INSERT INTO Transactions (account_id, person_id, transaction_date, transaction_type, amount, description) "
            "VALUES (?, ?, '2026-01-01', 'Credit', 1, ?)",
            (account_id, person_id, description),
        ).lastrowid
        conn.commit()
        conn.close()
        return transaction_id
    finally:
        database.DB_PATH, database.DATA_DIR = old_db_path, old_data_dir


def test_valid_application_backup_replaces_destination_and_closes_source(target_db, tmp_path):
    source = tmp_path / "backup.sqlite"
    _create_app_db(source, "backup person")
    transaction_id = _insert_deposit_transaction(source, "FD987654321098 credit")

    database.restore_database(str(source))

    assert _people(target_db) == ["backup person", "backfill fixture"]
    conn = sqlite3.connect(target_db)
    try:
        assert conn.execute(
            "SELECT deposit_account_no FROM Transactions WHERE transaction_id=?", (transaction_id,)
        ).fetchone()[0] == "987654321098"
    finally:
        conn.close()
    renamed = tmp_path / "backup-renamed.sqlite"
    source.rename(renamed)  # Proves the read-only source handle was closed.
    assert renamed.exists()


def test_stage_backfill_failure_never_writes_live_database(target_db, tmp_path, monkeypatch):
    source = tmp_path / "backup.sqlite"
    _create_app_db(source, "backup person")
    _insert_deposit_transaction(source, "FD987654321098 credit")
    live_transaction_id = _insert_deposit_transaction(target_db, "FD123456789012 live")
    original_init = database.initialise_database

    def fail_after_stage_backfill(conn=None):
        original_init(conn)
        raise RuntimeError("injected stage migration failure")

    monkeypatch.setattr(database, "initialise_database", fail_after_stage_backfill)
    with pytest.raises(RuntimeError, match="stage migration failure"):
        database.restore_database(str(source))

    conn = sqlite3.connect(target_db)
    try:
        assert conn.execute(
            "SELECT deposit_account_no FROM Transactions WHERE transaction_id=?", (live_transaction_id,)
        ).fetchone()[0] is None
    finally:
        conn.close()


def test_staging_migrations_do_not_redirect_application_db_path(target_db, tmp_path, monkeypatch):
    source = tmp_path / "backup.sqlite"
    _create_app_db(source, "backup person")
    original_init = database.initialise_database
    observed_paths = []

    def track_init(conn=None):
        observed_paths.append(database.DB_PATH)
        return original_init(conn)

    monkeypatch.setattr(database, "initialise_database", track_init)
    database.restore_database(str(source))
    assert observed_paths == [str(target_db)]
    assert _people(target_db) == ["backup person"]


@pytest.mark.parametrize("kind", ["empty", "unrelated", "corrupt", "incompatible"])
def test_invalid_backup_preserves_destination_and_releases_source(target_db, tmp_path, kind):
    source = tmp_path / f"{kind}.sqlite"
    if kind == "empty":
        conn = sqlite3.connect(source)
        conn.close()
    elif kind == "unrelated":
        conn = sqlite3.connect(source)
        conn.execute("CREATE TABLE notes (value TEXT)")
        conn.commit()
        conn.close()
    elif kind == "corrupt":
        source.write_bytes(b"not a sqlite database")
    else:
        conn = sqlite3.connect(source)
        conn.execute("CREATE TABLE AuthSecurity (auth_id INTEGER)")
        conn.execute("CREATE TABLE Person (person_id INTEGER, full_name TEXT)")
        conn.execute("CREATE TABLE BankAccount (account_id INTEGER, person_id INTEGER, bank_name TEXT)")
        conn.commit()
        conn.close()

    with pytest.raises((ValueError, sqlite3.DatabaseError)):
        database.restore_database(str(source))

    assert _people(target_db) == ["destination sentinel"]
    renamed = tmp_path / f"{kind}-renamed.sqlite"
    source.rename(renamed)
    assert renamed.exists()


def test_orphaned_backup_rows_are_rejected_without_changing_destination(target_db, tmp_path):
    source = tmp_path / "orphaned.sqlite"
    _create_app_db(source, "backup person")
    conn = sqlite3.connect(source)
    conn.execute(
        "INSERT INTO AccountHolder (account_id, person_id, is_primary) VALUES (987654, 876543, 1)"
    )
    conn.commit()
    conn.close()

    with pytest.raises(ValueError, match="foreign-key"):
        database.restore_database(str(source))

    assert _people(target_db) == ["destination sentinel"]
    source.rename(tmp_path / "orphaned-renamed.sqlite")


def test_same_source_and_destination_is_rejected_without_mutation(target_db):
    with pytest.raises(ValueError, match="same file"):
        database.restore_database(str(target_db))
    assert _people(target_db) == ["destination sentinel"]


def test_install_failure_restores_destination_snapshot(target_db, tmp_path, monkeypatch):
    source = tmp_path / "backup.sqlite"
    _create_app_db(source, "backup person")
    real_backup = database._sqlite_backup
    calls = 0

    def fail_after_install(source_conn, destination_conn):
        nonlocal calls
        calls += 1
        real_backup(source_conn, destination_conn)
        # Calls: source->stage, live->rollback, stage->live, rollback->live.
        if calls == 3:
            raise sqlite3.OperationalError("injected install failure")

    monkeypatch.setattr(database, "_sqlite_backup", fail_after_install)
    with pytest.raises(sqlite3.OperationalError, match="injected install failure"):
        database.restore_database(str(source))

    assert _people(target_db) == ["destination sentinel"]
    source.rename(tmp_path / "backup-renamed.sqlite")


def test_failed_rollback_retains_recovery_snapshot(target_db, tmp_path, monkeypatch):
    source = tmp_path / "backup.sqlite"
    _create_app_db(source, "backup person")
    real_backup = database._sqlite_backup
    calls = 0

    def fail_install_and_recovery(source_conn, destination_conn):
        nonlocal calls
        calls += 1
        if calls in (3, 4):
            raise sqlite3.OperationalError("injected backup failure")
        real_backup(source_conn, destination_conn)

    monkeypatch.setattr(database, "_sqlite_backup", fail_install_and_recovery)
    with pytest.raises(database.RestoreRecoveryError, match="recovery snapshot retained") as exc_info:
        database.restore_database(str(source))

    retained = list(target_db.parent.glob(".restore_rollback_*.sqlite"))
    assert len(retained) == 1
    assert exc_info.value.recovery_path == str(retained[0])
    assert _people(retained[0]) == ["destination sentinel"]
    source.rename(tmp_path / "backup-renamed.sqlite")
