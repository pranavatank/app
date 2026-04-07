"""
core/database.py — SQLite database initialisation and connection management.
All 9 tables are created here. The DB file lives at data/financial.db.
"""

import sqlite3
import os
from config import DB_PATH, DATA_DIR


def _migrate_fixed_deposit_schema_if_needed(conn: sqlite3.Connection, cur: sqlite3.Cursor) -> None:
    """Upgrade FixedDeposit table for nullable and calculation-method support."""
    info = cur.execute("PRAGMA table_info(FixedDeposit)").fetchall()
    if not info:
        return

    col_meta = {row[1]: row for row in info}
    needs_nullable_migration = False
    for col in ["start_date", "tenure_months", "interest_rate", "maturity_date", "maturity_amount"]:
        if col in col_meta and col_meta[col][3] == 1:  # notnull flag
            needs_nullable_migration = True
            break

    has_source_description = "source_description" in col_meta
    has_tenure_years = "tenure_years" in col_meta
    has_tenure_days = "tenure_days" in col_meta
    has_fd_reference_no = "fd_reference_no" in col_meta
    has_expected_interest_amount = "expected_interest_amount" in col_meta
    has_actual_interest_amount = "actual_interest_amount" in col_meta
    has_linked_transaction_id = "linked_transaction_id" in col_meta
    has_source_statement_file = "source_statement_file" in col_meta
    has_source_transaction_id = "source_transaction_id" in col_meta
    has_maturity_amount_formula = "maturity_amount_formula" in col_meta
    has_maturity_amount_bank = "maturity_amount_bank" in col_meta
    has_maturity_calc_method = "maturity_calc_method" in col_meta

    if needs_nullable_migration:
        conn.execute("PRAGMA foreign_keys=OFF")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS FixedDeposit_new (
                fd_id               INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id          INTEGER NOT NULL REFERENCES BankAccount(account_id),
                person_id           INTEGER NOT NULL REFERENCES Person(person_id),
                principal_amount    REAL    NOT NULL,
                start_date          TEXT,
                fd_reference_no     TEXT,
                tenure_years        INTEGER DEFAULT 0,
                tenure_months       INTEGER,
                tenure_days         INTEGER DEFAULT 0,
                interest_rate       REAL,
                compounding_type    TEXT    DEFAULT 'Quarterly',
                maturity_date       TEXT,
                maturity_amount     REAL,
                maturity_amount_formula REAL,
                maturity_amount_bank REAL,
                maturity_calc_method TEXT DEFAULT 'Formula',
                expected_interest_amount REAL DEFAULT 0,
                actual_interest_amount REAL DEFAULT 0,
                linked_transaction_id INTEGER REFERENCES Transactions(transaction_id),
                source_statement_file TEXT,
                source_transaction_id INTEGER REFERENCES Transactions(transaction_id),
                status              TEXT    NOT NULL DEFAULT 'Active',
                source_description  TEXT
            )
        """)

        fd_reference_expr = "fd_reference_no" if has_fd_reference_no else "NULL"
        tenure_years_expr = "COALESCE(tenure_years, 0)" if has_tenure_years else "0"
        tenure_days_expr = "COALESCE(tenure_days, 0)" if has_tenure_days else "0"
        maturity_amount_formula_expr = "maturity_amount_formula" if has_maturity_amount_formula else "maturity_amount"
        maturity_amount_bank_expr = "maturity_amount_bank" if has_maturity_amount_bank else "maturity_amount"
        maturity_calc_method_expr = "COALESCE(maturity_calc_method, 'Formula')" if has_maturity_calc_method else "'Formula'"
        expected_interest_expr = "expected_interest_amount" if has_expected_interest_amount else "0"
        actual_interest_expr = "actual_interest_amount" if has_actual_interest_amount else "0"
        linked_tx_expr = "linked_transaction_id" if has_linked_transaction_id else "NULL"
        source_file_expr = "source_statement_file" if has_source_statement_file else "NULL"
        source_tx_expr = "source_transaction_id" if has_source_transaction_id else "NULL"
        source_desc_expr = "source_description" if has_source_description else "NULL"

        cur.execute(f"""
            INSERT INTO FixedDeposit_new
                (fd_id, account_id, person_id, principal_amount, start_date,
                                 fd_reference_no,
                                 tenure_years, tenure_months, tenure_days,
                                 interest_rate, compounding_type,
                   maturity_date, maturity_amount, maturity_amount_formula,
                   maturity_amount_bank, maturity_calc_method,
                                     expected_interest_amount, actual_interest_amount,
                                     linked_transaction_id, source_statement_file, source_transaction_id,
                   status, source_description)
            SELECT fd_id, account_id, person_id, principal_amount, start_date,
                     {fd_reference_expr},
                     {tenure_years_expr}, tenure_months, {tenure_days_expr},
                     interest_rate, compounding_type,
                     maturity_date, maturity_amount, {maturity_amount_formula_expr},
                     {maturity_amount_bank_expr}, {maturity_calc_method_expr},
                     {expected_interest_expr}, {actual_interest_expr},
                     {linked_tx_expr}, {source_file_expr}, {source_tx_expr},
                     status, {source_desc_expr}
            FROM FixedDeposit
        """)

        cur.execute("DROP TABLE FixedDeposit")
        cur.execute("ALTER TABLE FixedDeposit_new RENAME TO FixedDeposit")
        conn.execute("PRAGMA foreign_keys=ON")
        return

    if not has_source_description:
        cur.execute("ALTER TABLE FixedDeposit ADD COLUMN source_description TEXT")
    if not has_tenure_years:
        cur.execute("ALTER TABLE FixedDeposit ADD COLUMN tenure_years INTEGER DEFAULT 0")
    if not has_tenure_days:
        cur.execute("ALTER TABLE FixedDeposit ADD COLUMN tenure_days INTEGER DEFAULT 0")
    if not has_fd_reference_no:
        cur.execute("ALTER TABLE FixedDeposit ADD COLUMN fd_reference_no TEXT")
    if not has_expected_interest_amount:
        cur.execute("ALTER TABLE FixedDeposit ADD COLUMN expected_interest_amount REAL DEFAULT 0")
    if not has_actual_interest_amount:
        cur.execute("ALTER TABLE FixedDeposit ADD COLUMN actual_interest_amount REAL DEFAULT 0")
    if not has_linked_transaction_id:
        cur.execute("ALTER TABLE FixedDeposit ADD COLUMN linked_transaction_id INTEGER")
    if not has_source_statement_file:
        cur.execute("ALTER TABLE FixedDeposit ADD COLUMN source_statement_file TEXT")
    if not has_source_transaction_id:
        cur.execute("ALTER TABLE FixedDeposit ADD COLUMN source_transaction_id INTEGER")
    if not has_maturity_amount_formula:
        cur.execute("ALTER TABLE FixedDeposit ADD COLUMN maturity_amount_formula REAL")
    if not has_maturity_amount_bank:
        cur.execute("ALTER TABLE FixedDeposit ADD COLUMN maturity_amount_bank REAL")
    if not has_maturity_calc_method:
        cur.execute("ALTER TABLE FixedDeposit ADD COLUMN maturity_calc_method TEXT DEFAULT 'Formula'")

    cur.execute("""
        UPDATE FixedDeposit
        SET tenure_years = COALESCE(tenure_years, 0),
            tenure_days = COALESCE(tenure_days, 0),
            maturity_amount_formula = COALESCE(maturity_amount_formula, maturity_amount),
            maturity_amount_bank = COALESCE(maturity_amount_bank, maturity_amount),
            maturity_calc_method = COALESCE(maturity_calc_method, 'Formula'),
            expected_interest_amount = COALESCE(expected_interest_amount, 0),
            actual_interest_amount = COALESCE(actual_interest_amount, 0)
    """)


def _migrate_fd_interest_record_schema_if_needed(cur: sqlite3.Cursor) -> None:
    cols = {row[1] for row in cur.execute("PRAGMA table_info(FDInterestRecord)").fetchall()}
    if "quarter" not in cols:
        cur.execute("ALTER TABLE FDInterestRecord ADD COLUMN quarter TEXT")
    if "period_start" not in cols:
        cur.execute("ALTER TABLE FDInterestRecord ADD COLUMN period_start TEXT")
    if "period_end" not in cols:
        cur.execute("ALTER TABLE FDInterestRecord ADD COLUMN period_end TEXT")


def _migrate_bank_account_schema_if_needed(cur: sqlite3.Cursor) -> None:
    """Upgrade older BankAccount schemas with newer optional fields."""
    cols = {row[1] for row in cur.execute("PRAGMA table_info(BankAccount)").fetchall()}
    if not cols:
        return

    column_defs = {
        "account_holder_name": "TEXT",
        "account_number_masked": "TEXT",
        "account_number_full": "TEXT",
        "ifsc_code": "TEXT",
        "micr_code": "TEXT",
        "customer_id": "TEXT",
        "ckyc_id": "TEXT",
        "branch_name": "TEXT",
        "branch_address": "TEXT",
        "communication_address": "TEXT",
        "email_id": "TEXT",
        "phone_no": "TEXT",
        "account_opening_date": "TEXT",
        "account_status": "TEXT DEFAULT 'Active'",
        "currency": "TEXT DEFAULT 'INR'",
        "nomination_status": "TEXT",
        "nominee_name": "TEXT",
        "debit_card_enabled": "INTEGER DEFAULT 0",
        "debit_card_charges": "REAL DEFAULT 0",
        "debit_card_effective_from": "TEXT",
        "opening_balance": "REAL NOT NULL DEFAULT 0",
        "current_balance": "REAL NOT NULL DEFAULT 0",
        "interest_rate": "REAL NOT NULL DEFAULT 0",
        "created_at": "TEXT",
    }

    for col, ddl in column_defs.items():
        if col not in cols:
            cur.execute(f"ALTER TABLE BankAccount ADD COLUMN {col} {ddl}")


def _migrate_transactions_schema_if_needed(cur: sqlite3.Cursor) -> None:
    """Upgrade older Transactions schemas with reference number support."""
    cols = {row[1] for row in cur.execute("PRAGMA table_info(Transactions)").fetchall()}
    if not cols:
        return

    if "reference_no" not in cols:
        cur.execute("ALTER TABLE Transactions ADD COLUMN reference_no TEXT")
    if "linked_transaction_id" not in cols:
        cur.execute("ALTER TABLE Transactions ADD COLUMN linked_transaction_id INTEGER")
    if "internal_transfer_group_id" not in cols:
        cur.execute("ALTER TABLE Transactions ADD COLUMN internal_transfer_group_id INTEGER")
    if "is_internal_transfer" not in cols:
        cur.execute("ALTER TABLE Transactions ADD COLUMN is_internal_transfer INTEGER NOT NULL DEFAULT 0")
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_Transactions_reference_no "
        "ON Transactions(reference_no)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_Transactions_internal_transfer "
        "ON Transactions(is_internal_transfer, internal_transfer_group_id)"
    )


def _migrate_person_schema_if_needed(cur: sqlite3.Cursor) -> None:
    """Upgrade older Person schemas with split name fields."""
    cols = {row[1] for row in cur.execute("PRAGMA table_info(Person)").fetchall()}
    if not cols:
        return

    if "first_name" not in cols:
        cur.execute("ALTER TABLE Person ADD COLUMN first_name TEXT")
    if "middle_name" not in cols:
        cur.execute("ALTER TABLE Person ADD COLUMN middle_name TEXT")
    if "last_name" not in cols:
        cur.execute("ALTER TABLE Person ADD COLUMN last_name TEXT")


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
            first_name    TEXT,
            middle_name   TEXT,
            last_name     TEXT,
            date_of_birth TEXT,
            pan_number    TEXT,
            contact_notes TEXT,
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
            reference_no     TEXT,
            description      TEXT,
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
            quarter         TEXT,
            period_start    TEXT,
            period_end      TEXT,
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

    _migrate_bank_account_schema_if_needed(cur)
    _migrate_transactions_schema_if_needed(cur)
    _migrate_fixed_deposit_schema_if_needed(conn, cur)
    _migrate_fd_interest_record_schema_if_needed(cur)

    conn.commit()
    conn.close()
    print("[DB] Database initialised successfully.")


def close_connection() -> None:
    """Close any open database connections."""
    # SQLite connections are per-thread, so this is mainly for cleanup
    pass
