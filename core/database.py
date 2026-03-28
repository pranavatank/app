"""
core/database.py — SQLite database initialisation and connection management.
All 9 tables are created here. The DB file lives at data/financial.db.
"""

import sqlite3
import os
from config import DB_PATH, DATA_DIR


def _migrate_fixed_deposit_schema_if_needed(conn: sqlite3.Connection, cur: sqlite3.Cursor) -> None:
    """Upgrade FixedDeposit table to allow NULL unknown values for statement-inferred FDs."""
    info = cur.execute("PRAGMA table_info(FixedDeposit)").fetchall()
    if not info:
        return

    col_meta = {row[1]: row for row in info}
    needs_nullable_migration = False
    for col in ["tenure_months", "interest_rate", "maturity_date", "maturity_amount"]:
        if col in col_meta and col_meta[col][3] == 1:  # notnull flag
            needs_nullable_migration = True
            break

    has_source_description = "source_description" in col_meta

    if needs_nullable_migration:
        conn.execute("PRAGMA foreign_keys=OFF")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS FixedDeposit_new (
                fd_id               INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id          INTEGER NOT NULL REFERENCES BankAccount(account_id),
                person_id           INTEGER NOT NULL REFERENCES Person(person_id),
                principal_amount    REAL    NOT NULL,
                start_date          TEXT    NOT NULL,
                tenure_months       INTEGER,
                interest_rate       REAL,
                compounding_type    TEXT    DEFAULT 'Quarterly',
                maturity_date       TEXT,
                maturity_amount     REAL,
                status              TEXT    NOT NULL DEFAULT 'Active',
                source_description  TEXT
            )
        """)

        cur.execute("""
            INSERT INTO FixedDeposit_new
                (fd_id, account_id, person_id, principal_amount, start_date,
                 tenure_months, interest_rate, compounding_type,
                 maturity_date, maturity_amount, status, source_description)
            SELECT fd_id, account_id, person_id, principal_amount, start_date,
                   tenure_months, interest_rate, compounding_type,
                   maturity_date, maturity_amount, status,
                   NULL
            FROM FixedDeposit
        """)

        cur.execute("DROP TABLE FixedDeposit")
        cur.execute("ALTER TABLE FixedDeposit_new RENAME TO FixedDeposit")
        conn.execute("PRAGMA foreign_keys=ON")
        return

    if not has_source_description:
        cur.execute("ALTER TABLE FixedDeposit ADD COLUMN source_description TEXT")


def get_connection() -> sqlite3.Connection:
    """Return a connection to the SQLite database."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row          # dict-like row access
    conn.execute("PRAGMA journal_mode=WAL") # better concurrency
    conn.execute("PRAGMA foreign_keys=ON")  # enforce FK constraints
    return conn


def initialise_database() -> None:
    """Create all tables if they do not already exist."""
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
            date_of_birth TEXT,
            pan_number    TEXT,
            contact_notes TEXT,
            created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # ── BankAccount ──────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS BankAccount (
            account_id          INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id           INTEGER NOT NULL REFERENCES Person(person_id),
            bank_name           TEXT    NOT NULL,
            account_type        TEXT    NOT NULL,
            account_number_masked TEXT,
            account_number_full TEXT,
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
            description      TEXT,
            balance_after    REAL,
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
            start_date        TEXT    NOT NULL,
            tenure_months     INTEGER,
            interest_rate     REAL,
            compounding_type  TEXT    DEFAULT 'Quarterly',
            maturity_date     TEXT,
            maturity_amount   REAL,
            status            TEXT    NOT NULL DEFAULT 'Active',
            source_description TEXT
        )
    """)

    # ── FDInterestRecord ─────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS FDInterestRecord (
            record_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            fd_id           INTEGER NOT NULL REFERENCES FixedDeposit(fd_id),
            financial_year  TEXT    NOT NULL,
            interest_earned REAL    NOT NULL,
            assessment_year TEXT    NOT NULL
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
            interest_earned     REAL    NOT NULL
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
            UNIQUE(person_id, financial_year)
        )
    """)

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

    _migrate_fixed_deposit_schema_if_needed(conn, cur)

    conn.commit()
    conn.close()
    print("[DB] Database initialised successfully.")


def close_connection() -> None:
    """Close any open database connections."""
    # SQLite connections are per-thread, so this is mainly for cleanup
    pass
