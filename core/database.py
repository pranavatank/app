"""
core/database.py — SQLite database initialisation and connection management.
All 9 tables are created here. The DB file lives at data/financial.db.

SECURITY NOTE:
The database file (data/financial.db) is stored as plaintext SQLite. This is intentional.
Only two columns are field-encrypted with AES-256:
  - BankAccount.statement_password_enc (bank statement password)
  - Person.ais_tis_password_enc (Income Tax portal password)
All other data (balances, transactions, fixed deposits, tax calculations, etc.) is in plaintext.
Anyone with read access to the file can inspect all financial data.
SQLCipher (encrypted SQLite) was considered and deferred; plaintext SQLite is the current choice.
For privacy from file-system access, store data/financial.db and backups/ on an encrypted volume.
"""

import sqlite3
import os
import tempfile
from pathlib import Path
from config import DB_PATH, DATA_DIR
from core.database_migrations import (
    _migrate_fixed_deposit_schema_if_needed,
    _migrate_fd_interest_record_schema_if_needed,
    _migrate_savings_interest_record_schema_if_needed,
    _migrate_tax_profile_schema_if_needed,
    _migrate_bank_account_schema_if_needed,
    _migrate_transactions_schema_if_needed,
    _migrate_person_schema_if_needed,
    _migrate_bank_account_to_account_holder_if_needed,
    _seed_bank_fd_conventions,
    _seed_tax_config,
)


class RestoreRecoveryError(RuntimeError):
    """Restore install failed and the live database could not be rolled back."""

    def __init__(self, recovery_path: str):
        self.recovery_path = recovery_path
        super().__init__(
            "Database restore could not be completed or rolled back; "
            f"recovery snapshot retained at {recovery_path}"
        )


def get_connection() -> sqlite3.Connection:
    """Return a connection to the SQLite database."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row          # dict-like row access
    conn.execute("PRAGMA journal_mode=WAL") # better concurrency
    conn.execute("PRAGMA foreign_keys=ON")  # enforce FK constraints
    return conn


def backup_database(dest_path: str) -> None:
    """Create a consistent backup of the live DB using SQLite backup API."""
    dest_dir = os.path.dirname(dest_path)
    if dest_dir:
        os.makedirs(dest_dir, exist_ok=True)

    src = get_connection()
    try:
        src.execute("PRAGMA wal_checkpoint(FULL)")
        with sqlite3.connect(dest_path) as dest:
            src.backup(dest)
            dest.commit()
    finally:
        src.close()


def restore_database(src_path: str) -> None:
    """Validate and stage an application backup before replacing the live DB.

    SQLite's backup API copies into the existing destination, so keep a second
    SQLite snapshot for recovery if installation or its verification fails.
    The input is opened read-only and all handles are closed on every path.
    """
    if not os.path.exists(src_path):
        raise FileNotFoundError(f"Backup not found: {src_path}")

    destination = os.path.abspath(DB_PATH)
    source = os.path.abspath(src_path)
    if os.path.normcase(os.path.realpath(source)) == os.path.normcase(os.path.realpath(destination)):
        raise ValueError("Backup source and database destination are the same file")

    stage_path = None
    rollback_path = None
    retain_rollback = False

    def temp_db_path(prefix):
        fd, path = tempfile.mkstemp(prefix=prefix, suffix=".sqlite", dir=os.path.dirname(destination) or ".")
        os.close(fd)
        os.unlink(path)
        return path

    def readonly_connection(path):
        return sqlite3.connect(f"{Path(path).resolve().as_uri()}?mode=ro", uri=True)

    def validate_application_db(conn):
        integrity = conn.execute("PRAGMA integrity_check").fetchone()
        if not integrity or integrity[0] != "ok":
            raise ValueError("Backup database failed SQLite integrity check")
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )}
        required = {"AuthSecurity", "Person", "BankAccount"}
        if not required.issubset(tables):
            raise ValueError("File is not a compatible application database backup")
        required_columns = {
            "AuthSecurity": {"auth_id", "password_hash", "password_salt", "device_id_hash"},
            "Person": {"person_id", "full_name"},
            "BankAccount": {"account_id", "person_id", "bank_name", "account_type"},
        }
        for table, columns in required_columns.items():
            actual = {row[1] for row in conn.execute(f"PRAGMA table_info([{table}])")}
            if not columns.issubset(actual):
                raise ValueError("File is not a compatible application database backup")

    def backup_file(src, dst):
        source_conn = None
        dest_conn = None
        try:
            source_conn = readonly_connection(src)
            dest_conn = sqlite3.connect(dst)
            _sqlite_backup(source_conn, dest_conn)
            dest_conn.commit()
        finally:
            if dest_conn is not None:
                dest_conn.close()
            if source_conn is not None:
                source_conn.close()

    try:
        # Read and validate before creating or opening the live destination.
        src_conn = readonly_connection(source)
        try:
            validate_application_db(src_conn)
            os.makedirs(os.path.dirname(destination) or ".", exist_ok=True)
            stage_path = temp_db_path(".restore_stage_")
            stage_conn = sqlite3.connect(stage_path)
            try:
                _sqlite_backup(src_conn, stage_conn)
                stage_conn.commit()
            finally:
                stage_conn.close()
        finally:
            src_conn.close()

        # Run only the application's known, idempotent schema upgrades on the
        # isolated copy. This preserves supported legacy backups without
        # guessing at unrelated schemas or touching the live database.
        stage_dir = os.path.dirname(stage_path) or "."
        migration_conn = sqlite3.connect(stage_path)
        migration_conn.row_factory = sqlite3.Row
        migration_conn.execute("PRAGMA foreign_keys=ON")
        try:
            initialise_database(migration_conn)
        finally:
            migration_conn.close()
        stage_check = readonly_connection(stage_path)
        try:
            validate_application_db(stage_check)
            fk_errors = stage_check.execute("PRAGMA foreign_key_check").fetchall()
            if fk_errors:
                raise ValueError("Backup database contains invalid foreign-key references")
        finally:
            stage_check.close()

        had_destination = os.path.exists(destination)
        if had_destination:
            rollback_path = temp_db_path(".restore_rollback_")
            # A failed snapshot means we cannot safely promise recovery, so do
            # not proceed with installation.
            backup_file(destination, rollback_path)

        dest_conn = None
        stage_conn = None
        try:
            stage_conn = readonly_connection(stage_path)
            dest_conn = sqlite3.connect(destination)
            _sqlite_backup(stage_conn, dest_conn)
            dest_conn.commit()
            check = dest_conn.execute("PRAGMA integrity_check").fetchone()
            if not check or check[0] != "ok":
                raise sqlite3.DatabaseError("Restored database failed integrity check")
            validate_application_db(dest_conn)
            dest_conn.execute("PRAGMA wal_checkpoint(FULL)")
        except Exception as install_error:
            if dest_conn is not None and had_destination and rollback_path:
                rollback_conn = None
                try:
                    rollback_conn = readonly_connection(rollback_path)
                    _sqlite_backup(rollback_conn, dest_conn)
                    dest_conn.commit()
                    dest_conn.execute("PRAGMA wal_checkpoint(FULL)")
                except Exception as recovery_error:
                    retain_rollback = True
                    raise RestoreRecoveryError(rollback_path) from recovery_error
                finally:
                    if rollback_conn is not None:
                        rollback_conn.close()
            elif not had_destination:
                if dest_conn is not None:
                    dest_conn.close()
                    dest_conn = None
                for suffix in ("", "-wal", "-shm"):
                    try:
                        os.unlink(destination + suffix)
                    except FileNotFoundError:
                        pass
            raise install_error
        finally:
            if stage_conn is not None:
                stage_conn.close()
            if dest_conn is not None:
                dest_conn.close()
    finally:
        for path in (stage_path, rollback_path):
            if path == rollback_path and retain_rollback:
                continue
            if path:
                for suffix in ("", "-wal", "-shm"):
                    try:
                        os.unlink(path + suffix)
                    except FileNotFoundError:
                        pass


def _sqlite_backup(source: sqlite3.Connection, destination: sqlite3.Connection) -> None:
    """Small indirection to make backup failures recoverable and testable."""
    source.backup(destination)


def initialise_database(conn: sqlite3.Connection | None = None) -> None:
    """Create all tables if they do not already exist."""
    owns_connection = conn is None
    if conn is None:
        conn = get_connection()
    cur = conn.cursor()

    # ── AuthSecurity ─────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS AuthSecurity (
            auth_id              INTEGER PRIMARY KEY AUTOINCREMENT,
            password_hash        TEXT    NOT NULL,
            password_salt        TEXT    NOT NULL,
            device_id_hash       TEXT    NOT NULL,
            totp_secret          TEXT,
            privacy_mode_enabled INTEGER NOT NULL DEFAULT 0
        )
    """)

    # ── Person ───────────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS Person (
            person_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name     TEXT    NOT NULL,
            first_name    TEXT,
            middle_name   TEXT,
            last_name     TEXT,
            date_of_birth TEXT,
            pan_number    TEXT,
            contact_notes TEXT,
            ais_tis_password_enc TEXT,
            created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)

    _migrate_person_schema_if_needed(cur)

    # ── BankAccount ──────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS BankAccount (
            account_id          INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id           INTEGER NOT NULL REFERENCES Person(person_id),
            bank_name           TEXT    NOT NULL,
            account_holder_name TEXT,
            account_type        TEXT    NOT NULL,
            account_number_masked TEXT,
            account_number_full TEXT,
            statement_password_enc TEXT,
            ifsc_code           TEXT,
            micr_code           TEXT,
            customer_id         TEXT,
            ckyc_id             TEXT,
            branch_name         TEXT,
            branch_address      TEXT,
            communication_address TEXT,
            email_id            TEXT,
            phone_no            TEXT,
            account_opening_date TEXT,
            account_status      TEXT    DEFAULT 'Active',
            currency            TEXT    DEFAULT 'INR',
            nomination_status   TEXT,
            nominee_name        TEXT,
            debit_card_enabled  INTEGER DEFAULT 0,
            debit_card_charges  REAL    DEFAULT 0,
            debit_card_effective_from TEXT,
            opening_balance     REAL    NOT NULL DEFAULT 0,
            current_balance     REAL    NOT NULL DEFAULT 0,
            interest_rate       REAL    NOT NULL DEFAULT 0,
            created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # ── AccountHolder ────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS AccountHolder (
            account_id  INTEGER NOT NULL REFERENCES BankAccount(account_id),
            person_id   INTEGER NOT NULL REFERENCES Person(person_id),
            is_primary  INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (account_id, person_id)
        )
    """)

    # ── Transaction ──────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS Transactions (
            transaction_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id       INTEGER NOT NULL REFERENCES BankAccount(account_id),
            person_id        INTEGER NOT NULL REFERENCES Person(person_id),
            transaction_date TEXT    NOT NULL,
            transaction_type TEXT    NOT NULL,
            category         TEXT,
            mode             TEXT,
            amount           REAL    NOT NULL,
            reference_no     TEXT,
            description      TEXT,
            deposit_account_no TEXT,
            balance_after    REAL,
            linked_transaction_id INTEGER REFERENCES Transactions(transaction_id),
            internal_transfer_group_id INTEGER,
            is_internal_transfer INTEGER NOT NULL DEFAULT 0,
            source           TEXT    NOT NULL DEFAULT 'Manual',
            created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # ── FixedDeposit ─────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS FixedDeposit (
            fd_id             INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id        INTEGER NOT NULL REFERENCES BankAccount(account_id),
            person_id         INTEGER NOT NULL REFERENCES Person(person_id),
            principal_amount  REAL    NOT NULL,
            start_date        TEXT,
            fd_reference_no   TEXT,
            tenure_years      INTEGER DEFAULT 0,
            tenure_months     INTEGER,
            tenure_days       INTEGER DEFAULT 0,
            interest_rate     REAL,
            compounding_type  TEXT    DEFAULT 'Quarterly',
            maturity_date     TEXT,
            maturity_amount   REAL,
            maturity_amount_formula REAL,
            maturity_amount_bank REAL,
            maturity_calc_method TEXT DEFAULT 'Formula',
            expected_interest_amount REAL DEFAULT 0,
            actual_interest_amount REAL DEFAULT 0,
            linked_transaction_id INTEGER REFERENCES Transactions(transaction_id),
            source_statement_file TEXT,
            source_transaction_id INTEGER REFERENCES Transactions(transaction_id),
            deposit_account_no TEXT,
            status            TEXT    NOT NULL DEFAULT 'Active',
            source_description TEXT
        )
    """)

    # Run migrations BEFORE creating indexes so existing databases gain missing columns
    _migrate_transactions_schema_if_needed(cur)
    _migrate_fixed_deposit_schema_if_needed(conn, cur)
    _migrate_bank_account_to_account_holder_if_needed(conn, cur)

    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_FixedDeposit_deposit_account_no "
        "ON FixedDeposit(deposit_account_no)"
    )

    # ── FDInterestRecord ─────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS FDInterestRecord (
            record_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            fd_id           INTEGER NOT NULL REFERENCES FixedDeposit(fd_id),
            financial_year  TEXT    NOT NULL,
            quarter         TEXT,
            period_start    TEXT,
            period_end      TEXT,
            interest_earned REAL    NOT NULL,
            assessment_year TEXT    NOT NULL,
            tds_declaration_form TEXT
        )
    """)

    # ── SavingsInterestRecord ────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS SavingsInterestRecord (
            record_id           INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id          INTEGER NOT NULL REFERENCES BankAccount(account_id),
            financial_year      TEXT    NOT NULL,
            avg_monthly_balance REAL    NOT NULL,
            interest_rate       REAL    NOT NULL,
            interest_earned     REAL    NOT NULL,
            quarter             TEXT,
            daily_product       INTEGER NOT NULL DEFAULT 0,
            calculation_basis   TEXT
        )
    """)

    # ── TaxProfile ───────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS TaxProfile (
            tax_id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id                INTEGER NOT NULL REFERENCES Person(person_id),
            financial_year           TEXT    NOT NULL,
            salary_income            REAL    NOT NULL DEFAULT 0,
            fd_interest_income       REAL    NOT NULL DEFAULT 0,
            savings_interest_income  REAL    NOT NULL DEFAULT 0,
            other_income             REAL    NOT NULL DEFAULT 0,
            gross_total_income       REAL    NOT NULL DEFAULT 0,
            deductions_80c           REAL    NOT NULL DEFAULT 0,
            deductions_80d           REAL    NOT NULL DEFAULT 0,
            home_loan_interest       REAL    NOT NULL DEFAULT 0,
            hra_exemption            REAL    NOT NULL DEFAULT 0,
            standard_deduction       REAL    NOT NULL DEFAULT 50000,
            taxable_income_old_regime REAL   NOT NULL DEFAULT 0,
            taxable_income_new_regime REAL   NOT NULL DEFAULT 0,
            tax_old_regime           REAL    NOT NULL DEFAULT 0,
            tax_new_regime           REAL    NOT NULL DEFAULT 0,
            cess_amount              REAL    NOT NULL DEFAULT 0,
            total_tax_old            REAL    NOT NULL DEFAULT 0,
            total_tax_new            REAL    NOT NULL DEFAULT 0,
            rebate_87a_old           REAL    NOT NULL DEFAULT 0,
            rebate_87a_new           REAL    NOT NULL DEFAULT 0,
            tds_deducted             REAL    NOT NULL DEFAULT 0,
            tcs_collected            REAL    NOT NULL DEFAULT 0,
            advance_tax_paid         REAL    NOT NULL DEFAULT 0,
            self_assessment_tax      REAL    NOT NULL DEFAULT 0,
            UNIQUE(person_id, financial_year)
        )
    """)
    _migrate_tax_profile_schema_if_needed(cur)

    # ── StatementImportLog ───────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS StatementImportLog (
            import_id        INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id       INTEGER NOT NULL REFERENCES BankAccount(account_id),
            person_id        INTEGER NOT NULL REFERENCES Person(person_id),
            bank_name        TEXT    NOT NULL,
            file_name        TEXT    NOT NULL,
            file_type        TEXT    NOT NULL,
            import_date      TEXT    NOT NULL DEFAULT (datetime('now')),
            records_imported INTEGER NOT NULL DEFAULT 0,
            status           TEXT    NOT NULL DEFAULT 'Success'
        )
    """)

    # ── IncomeExpectation ────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS IncomeExpectation (
            expectation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER NOT NULL REFERENCES Person(person_id),
            account_id INTEGER NOT NULL REFERENCES BankAccount(account_id),
            income_type TEXT NOT NULL,
            expected_amount REAL NOT NULL,
            expected_date TEXT NOT NULL,
            frequency TEXT NOT NULL,
            financial_year TEXT NOT NULL,
            actual_transaction_id INTEGER REFERENCES Transactions(transaction_id),
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # ── Bank ─────────────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS Bank (
            bank_id INTEGER PRIMARY KEY AUTOINCREMENT,
            bank_name TEXT NOT NULL UNIQUE,
            nickname TEXT,
            tan_code TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Bank table migration for older DBs
    bank_cols = {row[1] for row in cur.execute("PRAGMA table_info(Bank)").fetchall()}
    if "nickname" not in bank_cols:
        cur.execute("ALTER TABLE Bank ADD COLUMN nickname TEXT")
    if "tan_code" not in bank_cols:
        cur.execute("ALTER TABLE Bank ADD COLUMN tan_code TEXT")
    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_Bank_tan_code_unique "
        "ON Bank(tan_code) WHERE tan_code IS NOT NULL AND tan_code <> ''"
    )

    # ── AISTISImport ─────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS AISTISImport (
            import_id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER NOT NULL REFERENCES Person(person_id),
            financial_year TEXT NOT NULL,
            import_date TEXT NOT NULL DEFAULT (datetime('now')),
            source_type TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            salary_income REAL DEFAULT 0,
            fd_interest REAL DEFAULT 0,
            savings_interest REAL DEFAULT 0,
            other_interest REAL DEFAULT 0,
            dividend_income REAL DEFAULT 0,
            rental_income REAL DEFAULT 0,
            other_income REAL DEFAULT 0,
            tds_deducted REAL DEFAULT 0,
            UNIQUE(person_id, financial_year, source_type)
        )
    """)

    # ── AISTISImportLine ─────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS AISTISImportLine (
            line_id INTEGER PRIMARY KEY AUTOINCREMENT,
            import_id INTEGER NOT NULL REFERENCES AISTISImport(import_id) ON DELETE CASCADE,
            line_no INTEGER NOT NULL,
            text TEXT NOT NULL
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_AISTISImportLine_import_id ON AISTISImportLine(import_id)")

    # ── AISTISImportRecord ───────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS AISTISImportRecord (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            import_id INTEGER NOT NULL REFERENCES AISTISImport(import_id) ON DELETE CASCADE,
            record_type TEXT NOT NULL,
            information_code TEXT,
            information_description TEXT,
            information_source TEXT,
            source_tan TEXT,
            bucket TEXT,
            count INTEGER,
            amount REAL,
            amount_reported REAL,
            amount_processed REAL,
            amount_accepted REAL,
            quarter TEXT,
            payment_date TEXT,
            amount_paid REAL,
            tds_deducted REAL,
            tds_deposited REAL,
            status TEXT,
            raw_line TEXT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_AISTISImportRecord_import_id ON AISTISImportRecord(import_id)")

    # Migrate older AISTISImportRecord schema if table existed without newer columns.
    ais_record_cols = {row[1] for row in cur.execute("PRAGMA table_info(AISTISImportRecord)").fetchall()}
    if "source_tan" not in ais_record_cols:
        cur.execute("ALTER TABLE AISTISImportRecord ADD COLUMN source_tan TEXT")
    if "amount_reported" not in ais_record_cols:
        cur.execute("ALTER TABLE AISTISImportRecord ADD COLUMN amount_reported REAL")
    if "amount_processed" not in ais_record_cols:
        cur.execute("ALTER TABLE AISTISImportRecord ADD COLUMN amount_processed REAL")
    if "amount_accepted" not in ais_record_cols:
        cur.execute("ALTER TABLE AISTISImportRecord ADD COLUMN amount_accepted REAL")

    # ── Form26ASImport ──────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS Form26ASImport (
            import_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id      INTEGER NOT NULL REFERENCES Person(person_id),
            financial_year TEXT    NOT NULL,
            import_date    TEXT    NOT NULL DEFAULT (datetime('now')),
            source_file    TEXT,
            total_tds      REAL    DEFAULT 0,
            raw_text       TEXT
        )
    """)

    # ── Form26ASRecord ──────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS Form26ASRecord (
            record_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            import_id      INTEGER NOT NULL REFERENCES Form26ASImport(import_id) ON DELETE CASCADE,
            section        TEXT,
            deductor_name  TEXT,
            deductor_tan   TEXT,
            transaction_date TEXT,
            amount_paid    REAL   DEFAULT 0,
            tds_deducted   REAL   DEFAULT 0,
            tds_deposited  REAL   DEFAULT 0,
            status         TEXT,
            certificate_no TEXT,
            remarks        TEXT,
            raw_line       TEXT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_Form26ASRecord_import ON Form26ASRecord(import_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_Form26ASRecord_tan    ON Form26ASRecord(deductor_tan)")

    # ── IncomeSource ────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS IncomeSource (
            source_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL,
            source_name TEXT NOT NULL,
            tan TEXT,
            pan TEXT,
            address TEXT,
            contact_person TEXT,
            phone TEXT,
            email TEXT,
            notes TEXT,
            created_date TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(tan)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_IncomeSource_tan ON IncomeSource(tan)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_IncomeSource_type ON IncomeSource(source_type)")

    # ── TaxSlabConfig ───────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS TaxSlabConfig (
            slab_id           INTEGER PRIMARY KEY AUTOINCREMENT,
            financial_year    TEXT    NOT NULL,
            regime            TEXT    NOT NULL,
            upper_limit       REAL,
            rate              REAL    NOT NULL,
            sort_order        INTEGER NOT NULL,
            UNIQUE(financial_year, regime, sort_order)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_TaxSlabConfig_fy_regime ON TaxSlabConfig(financial_year, regime)")

    # ── TaxParams ───────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS TaxParams (
            param_id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            financial_year           TEXT    NOT NULL UNIQUE,
            rebate_87a_limit         REAL    NOT NULL,
            rebate_87a_max           REAL    NOT NULL,
            standard_deduction       REAL    NOT NULL,
            cess_rate                REAL    NOT NULL,
            fd_tds_threshold         REAL    NOT NULL,
            fd_tds_threshold_senior  REAL    NOT NULL
        )
    """)

    # ── BankFDConvention ────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS BankFDConvention (
            convention_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            bank_id             INTEGER NOT NULL REFERENCES Bank(bank_id),
            compounding         TEXT    NOT NULL DEFAULT 'Quarterly',
            simple_below_days   INTEGER NOT NULL DEFAULT 183,
            day_count           TEXT    NOT NULL DEFAULT 'Actual/365',
            rounding_adjustment REAL    NOT NULL DEFAULT 4,
            UNIQUE(bank_id)
        )
    """)

    # Seed TaxSlabConfig and TaxParams if they don't exist
    _seed_tax_config(cur)
    _seed_bank_fd_conventions(cur)

    _migrate_bank_account_schema_if_needed(cur)
    _migrate_fd_interest_record_schema_if_needed(cur)
    _migrate_savings_interest_record_schema_if_needed(cur)

    # Run transaction backfill against the same database connection as schema
    # initialization. This is essential when initializing an isolated staged
    # restore copy and avoids routing writes through the process-wide DB path.
    from models.transaction import backfill_deposit_account_numbers
    backfill_deposit_account_numbers(conn)

    conn.commit()
    if owns_connection:
        conn.close()

    print("[DB] Database initialised successfully.")


def close_connection() -> None:
    """Close any open database connections."""
    # SQLite connections are per-thread, so this is mainly for cleanup
    pass
