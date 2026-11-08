"""Schema migrations and seed data for the SQLite database.

These helpers operate on the connection/cursor supplied by database initialisation;
they do not open connections or commit transactions.
"""

import sqlite3

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
    has_deposit_account_no = "deposit_account_no" in col_meta

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
        deposit_account_expr = "deposit_account_no" if has_deposit_account_no else "NULL"

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
                   deposit_account_no,
                   status, source_description)
            SELECT fd_id, account_id, person_id, principal_amount, start_date,
                     {fd_reference_expr},
                     {tenure_years_expr}, tenure_months, {tenure_days_expr},
                     interest_rate, compounding_type,
                     maturity_date, maturity_amount, {maturity_amount_formula_expr},
                     {maturity_amount_bank_expr}, {maturity_calc_method_expr},
                     {expected_interest_expr}, {actual_interest_expr},
                     {linked_tx_expr}, {source_file_expr}, {source_tx_expr},
                     {deposit_account_expr},
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
    if not has_deposit_account_no:
        cur.execute("ALTER TABLE FixedDeposit ADD COLUMN deposit_account_no TEXT")

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
    if "tds_declaration_form" not in cols:
        cur.execute("ALTER TABLE FDInterestRecord ADD COLUMN tds_declaration_form TEXT")


def _migrate_savings_interest_record_schema_if_needed(cur: sqlite3.Cursor) -> None:
    """Upgrade SavingsInterestRecord schema to support daily-product calculation."""
    cols = {row[1] for row in cur.execute("PRAGMA table_info(SavingsInterestRecord)").fetchall()}
    if "quarter" not in cols:
        cur.execute("ALTER TABLE SavingsInterestRecord ADD COLUMN quarter TEXT")
    if "daily_product" not in cols:
        cur.execute("ALTER TABLE SavingsInterestRecord ADD COLUMN daily_product INTEGER NOT NULL DEFAULT 0")
    if "calculation_basis" not in cols:
        cur.execute("ALTER TABLE SavingsInterestRecord ADD COLUMN calculation_basis TEXT")


def _migrate_tax_profile_schema_if_needed(cur: sqlite3.Cursor) -> None:
    """Upgrade older TaxProfile schemas with rebate/tax-paid tracking columns."""
    cols = {row[1] for row in cur.execute("PRAGMA table_info(TaxProfile)").fetchall()}
    if not cols:
        return
    for col, ddl in [
        ("rebate_87a_old", "REAL NOT NULL DEFAULT 0"),
        ("rebate_87a_new", "REAL NOT NULL DEFAULT 0"),
        ("tds_deducted", "REAL NOT NULL DEFAULT 0"),
        ("tcs_collected", "REAL NOT NULL DEFAULT 0"),
        ("advance_tax_paid", "REAL NOT NULL DEFAULT 0"),
        ("self_assessment_tax", "REAL NOT NULL DEFAULT 0"),
    ]:
        if col not in cols:
            cur.execute(f"ALTER TABLE TaxProfile ADD COLUMN {col} {ddl}")


def _migrate_bank_account_schema_if_needed(cur: sqlite3.Cursor) -> None:
    """Upgrade older BankAccount schemas with newer optional fields."""
    cols = {row[1] for row in cur.execute("PRAGMA table_info(BankAccount)").fetchall()}
    if not cols:
        return

    column_defs = {
        "account_holder_name": "TEXT",
        "account_number_masked": "TEXT",
        "account_number_full": "TEXT",
        "statement_password_enc": "TEXT",
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
    if "deposit_account_no" not in cols:
        cur.execute("ALTER TABLE Transactions ADD COLUMN deposit_account_no TEXT")
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_Transactions_reference_no "
        "ON Transactions(reference_no)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_Transactions_internal_transfer "
        "ON Transactions(is_internal_transfer, internal_transfer_group_id)"
    )


def _migrate_person_schema_if_needed(cur: sqlite3.Cursor) -> None:
    """Upgrade older Person schemas with split name fields and entity_type."""
    cols = {row[1] for row in cur.execute("PRAGMA table_info(Person)").fetchall()}
    if not cols:
        return

    if "first_name" not in cols:
        cur.execute("ALTER TABLE Person ADD COLUMN first_name TEXT")
    if "middle_name" not in cols:
        cur.execute("ALTER TABLE Person ADD COLUMN middle_name TEXT")
    if "last_name" not in cols:
        cur.execute("ALTER TABLE Person ADD COLUMN last_name TEXT")
    if "ais_tis_password_enc" not in cols:
        cur.execute("ALTER TABLE Person ADD COLUMN ais_tis_password_enc TEXT")
    if "entity_type" not in cols:
        cur.execute("ALTER TABLE Person ADD COLUMN entity_type TEXT DEFAULT 'Individual'")


def _migrate_bank_account_to_account_holder_if_needed(conn: sqlite3.Connection, cur: sqlite3.Cursor) -> None:
    """
    Migrate existing BankAccount.person_id rows into AccountHolder as primary holder.
    The person_id column is deliberately RETAINED so existing queries keep working.
    This function is idempotent: running it multiple times is safe.
    """
    # Check if AccountHolder table exists
    table_info = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='AccountHolder'"
    ).fetchone()

    if not table_info:
        return  # Table doesn't exist yet, nothing to migrate

    # Check if any rows exist in AccountHolder
    count = cur.execute("SELECT COUNT(*) FROM AccountHolder").fetchone()[0]
    if count > 0:
        return  # Already migrated, idempotent

    # Get all BankAccount rows
    rows = cur.execute("""
        SELECT DISTINCT account_id, person_id
        FROM BankAccount
        WHERE person_id IS NOT NULL
    """).fetchall()

    for row in rows:
        account_id = row[0]
        person_id = row[1]

        # Check if this holder already exists (shouldn't happen, but be safe)
        existing = cur.execute("""
            SELECT COUNT(*) FROM AccountHolder
            WHERE account_id = ? AND person_id = ?
        """, (account_id, person_id)).fetchone()[0]

        if existing == 0:
            cur.execute("""
                INSERT INTO AccountHolder (account_id, person_id, is_primary)
                VALUES (?, ?, 1)
            """, (account_id, person_id))


def _seed_bank_fd_conventions(cur: sqlite3.Cursor) -> None:
    """Seed BankFDConvention table with default conventions for all banks (idempotent)."""
    # Get all banks from the Bank table
    banks = cur.execute("SELECT bank_id, bank_name FROM Bank").fetchall()

    for bank in banks:
        bank_id = bank[0]

        # Check if convention already exists for this bank
        existing = cur.execute(
            "SELECT COUNT(*) FROM BankFDConvention WHERE bank_id = ?",
            (bank_id,)
        ).fetchone()[0]

        if existing == 0:
            # Insert default convention
            cur.execute("""
                INSERT INTO BankFDConvention (bank_id, compounding, simple_below_days, day_count, rounding_adjustment)
                VALUES (?, ?, ?, ?, ?)
            """, (bank_id, 'Quarterly', 183, 'Actual/365', 4))


def _seed_tax_config(cur: sqlite3.Cursor) -> None:
    """Seed TaxSlabConfig and TaxParams with FY2025-26 and FY2026-27 data (idempotent)."""

    # Define New Regime slabs (identical for both FY2025-26 and FY2026-27)
    new_regime_slabs = [
        (400000, 0, 1),
        (800000, 5, 2),
        (1200000, 10, 3),
        (1600000, 15, 4),
        (2000000, 20, 5),
        (2400000, 25, 6),
        (None, 30, 7),  # Top slab, no upper limit
    ]

    years = ["2025-26", "2026-27"]

    for fy in years:
        # Check if this FY already has slabs
        existing = cur.execute(
            "SELECT COUNT(*) FROM TaxSlabConfig WHERE financial_year = ? AND regime = ?",
            (fy, "new")
        ).fetchone()[0]

        if existing == 0:
            for upper_limit, rate, sort_order in new_regime_slabs:
                cur.execute("""
                    INSERT INTO TaxSlabConfig (financial_year, regime, upper_limit, rate, sort_order)
                    VALUES (?, ?, ?, ?, ?)
                """, (fy, "new", upper_limit, rate, sort_order))

        # Check if TaxParams exist for this FY
        existing_params = cur.execute(
            "SELECT COUNT(*) FROM TaxParams WHERE financial_year = ?", (fy,)
        ).fetchone()[0]

        if existing_params == 0:
            cur.execute("""
                INSERT INTO TaxParams
                (financial_year, rebate_87a_limit, rebate_87a_max, standard_deduction, cess_rate, fd_tds_threshold, fd_tds_threshold_senior)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (fy, 1200000, 60000, 75000, 4, 50000, 100000))
