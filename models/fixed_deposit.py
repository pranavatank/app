"""
models/fixed_deposit.py — CRUD for the FixedDeposit table.
"""

import re
from typing import Optional

from core.database import get_connection


def add_fd(account_id: int, person_id: int, principal_amount: float,
           start_date: str, tenure_months: int, interest_rate: float,
           compounding_type: str, maturity_date: str,
           maturity_amount: float,
           maturity_amount_formula: float | None = None,
           maturity_amount_bank: float | None = None,
           maturity_calc_method: str = "Formula",
           tenure_years: int = 0,
           tenure_days: int = 0,
           fd_reference_no: str | None = None,
           expected_interest_amount: float | None = None,
           actual_interest_amount: float | None = None,
           linked_transaction_id: int | None = None,
           source_statement_file: str | None = None,
           source_transaction_id: int | None = None) -> int:
    """Insert a Fixed Deposit record. Returns new fd_id."""
    conn = get_connection()
    cur = conn.execute("""
        INSERT INTO FixedDeposit
            (account_id, person_id, principal_amount, start_date,
             fd_reference_no, tenure_years, tenure_months, tenure_days,
             interest_rate, compounding_type,
                         maturity_date, maturity_amount, maturity_amount_formula,
                 maturity_amount_bank, maturity_calc_method,
                 expected_interest_amount, actual_interest_amount,
                 linked_transaction_id, source_statement_file, source_transaction_id,
                 status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Active')
    """, (account_id, person_id, principal_amount, start_date,
            (fd_reference_no or None),
            tenure_years, tenure_months, tenure_days,
            interest_rate, compounding_type,
                    maturity_date, maturity_amount, maturity_amount_formula,
                maturity_amount_bank, maturity_calc_method,
            expected_interest_amount,
            actual_interest_amount,
            linked_transaction_id,
            source_statement_file,
            source_transaction_id))
    conn.commit()
    fd_id = cur.lastrowid
    conn.close()
    return fd_id


def fd_exists_for_statement(account_id: int, person_id: int,
                            principal_amount: float, start_date: str,
                            fd_reference_no: str | None = None,
                            source_transaction_id: int | None = None) -> bool:
    """Best-effort duplicate check for statement-created FD entries."""
    conn = get_connection()
    if source_transaction_id is not None:
        row = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM FixedDeposit
            WHERE account_id = ?
              AND person_id = ?
              AND source_transaction_id = ?
            """,
            (account_id, person_id, source_transaction_id),
        ).fetchone()
        if row["cnt"] > 0:
            conn.close()
            return True

    if fd_reference_no:
        row = conn.execute("""
            SELECT COUNT(*) AS cnt
            FROM FixedDeposit
            WHERE account_id = ?
              AND person_id = ?
              AND fd_reference_no = ?
              AND status IN ('Active', 'Pending Details')
        """, (account_id, person_id, fd_reference_no)).fetchone()
    elif source_transaction_id is None:
        row = conn.execute("""
            SELECT COUNT(*) AS cnt
            FROM FixedDeposit
            WHERE account_id = ?
              AND person_id = ?
              AND principal_amount = ?
              AND start_date = ?
              AND status IN ('Active', 'Pending Details')
        """, (account_id, person_id, principal_amount, start_date)).fetchone()
    conn.close()
    return row["cnt"] > 0


def add_fd_from_statement(account_id: int, person_id: int, principal_amount: float,
                          start_date: str,
                          fd_reference_no: Optional[str] = None,
                          tenure_years: Optional[int] = None,
                          tenure_months: Optional[int] = None,
                          tenure_days: Optional[int] = None,
                          interest_rate: Optional[float] = None,
                          compounding_type: Optional[str] = None,
                          maturity_date: Optional[str] = None,
                          maturity_amount: Optional[float] = None,
                          maturity_amount_formula: Optional[float] = None,
                          maturity_amount_bank: Optional[float] = None,
                          maturity_calc_method: str = "Formula",
                          source_description: Optional[str] = None,
                          expected_interest_amount: Optional[float] = None,
                          actual_interest_amount: Optional[float] = None,
                          linked_transaction_id: Optional[int] = None,
                          source_statement_file: Optional[str] = None,
                          source_transaction_id: Optional[int] = None) -> int:
    """
    Insert an FD inferred from statement narration.
    Unknown details remain NULL by design and can be filled later.
    Returns fd_id, or 0 if a likely duplicate already exists.
    """
    if fd_exists_for_statement(
        account_id,
        person_id,
        principal_amount,
        start_date,
        fd_reference_no,
        source_transaction_id,
    ):
        return 0

    conn = get_connection()
    cur = conn.execute("""
        INSERT INTO FixedDeposit
            (account_id, person_id, principal_amount, start_date,
             fd_reference_no,
             tenure_years, tenure_months, tenure_days,
             interest_rate, compounding_type,
             maturity_date, maturity_amount, maturity_amount_formula,
             maturity_amount_bank, maturity_calc_method,
             expected_interest_amount, actual_interest_amount,
             linked_transaction_id, source_statement_file, source_transaction_id,
             status, source_description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        account_id,
        person_id,
        principal_amount,
        start_date,
        (fd_reference_no or None),
        tenure_years,
        tenure_months,
        tenure_days,
        interest_rate,
        compounding_type,
        maturity_date,
        maturity_amount,
        maturity_amount_formula,
        maturity_amount_bank,
        maturity_calc_method,
        expected_interest_amount,
        actual_interest_amount,
        linked_transaction_id,
        source_statement_file,
        source_transaction_id,
        "Pending Details",
        (source_description or "")[:500],
    ))
    conn.commit()
    fd_id = cur.lastrowid
    conn.close()
    return fd_id


def get_all_fds(person_id: int = None, status: str = None) -> list[dict]:
    """Return FDs with optional person and status filters."""
    query  = """
        SELECT fd.*, ba.bank_name, p.full_name AS person_name
        FROM FixedDeposit fd
        JOIN BankAccount ba ON fd.account_id = ba.account_id
        JOIN Person p ON fd.person_id = p.person_id
        WHERE 1=1
    """
    params = []
    if person_id:
        query += " AND fd.person_id = ?"
        params.append(person_id)
    if status:
        query += " AND fd.status = ?"
        params.append(status)
    query += " ORDER BY fd.maturity_date"

    conn = get_connection()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_fd(fd_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM FixedDeposit WHERE fd_id = ?", (fd_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_fd_status(fd_id: int, status: str) -> None:
    """Update FD status: Active / Matured / Closed."""
    conn = get_connection()
    conn.execute(
        "UPDATE FixedDeposit SET status = ? WHERE fd_id = ?", (status, fd_id)
    )
    conn.commit()
    conn.close()


def update_fd(fd_id: int, principal_amount: float, start_date: str,
              tenure_months: int, interest_rate: float,
              compounding_type: str, maturity_date: str,
                            maturity_amount: float, status: str,
                            maturity_amount_formula: float | None = None,
                            maturity_amount_bank: float | None = None,
                            maturity_calc_method: str = "Formula",
                            tenure_years: int = 0,
                            tenure_days: int = 0,
                            fd_reference_no: str | None = None,
                            expected_interest_amount: float | None = None,
                            actual_interest_amount: float | None = None,
                            linked_transaction_id: int | None = None,
                            source_statement_file: str | None = None,
                            source_transaction_id: int | None = None) -> None:
    conn = get_connection()
    conn.execute("""
        UPDATE FixedDeposit
        SET principal_amount = ?, start_date = ?, fd_reference_no = ?,
            tenure_years = ?, tenure_months = ?, tenure_days = ?,
            interest_rate = ?, compounding_type = ?, maturity_date = ?,
                        maturity_amount = ?, maturity_amount_formula = ?,
                        maturity_amount_bank = ?, maturity_calc_method = ?,
                        expected_interest_amount = ?, actual_interest_amount = ?,
                        linked_transaction_id = ?, source_statement_file = ?, source_transaction_id = ?,
                        status = ?
        WHERE fd_id = ?
    """, (principal_amount, start_date, (fd_reference_no or None), tenure_years, tenure_months, tenure_days, interest_rate,
                    compounding_type, maturity_date, maturity_amount,
                    maturity_amount_formula, maturity_amount_bank,
                    maturity_calc_method, expected_interest_amount, actual_interest_amount,
                    linked_transaction_id, source_statement_file, source_transaction_id,
                    status, fd_id))
    conn.commit()
    conn.close()


def link_fd_transaction(fd_id: int, transaction_id: int) -> None:
    conn = get_connection()
    txn = conn.execute(
        "SELECT amount, transaction_type, category FROM Transactions WHERE transaction_id = ?",
        (transaction_id,),
    ).fetchone()
    if txn:
        actual_interest = txn["amount"] if txn["transaction_type"] == "Income" else None
        conn.execute(
            """
            UPDATE FixedDeposit
            SET linked_transaction_id = ?,
                actual_interest_amount = COALESCE(?, actual_interest_amount)
            WHERE fd_id = ?
            """,
            (transaction_id, actual_interest, fd_id),
        )
        conn.commit()
    conn.close()


def unlink_fd_transaction(fd_id: int) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE FixedDeposit SET linked_transaction_id = NULL WHERE fd_id = ?",
        (fd_id,),
    )
    conn.commit()
    conn.close()


def get_fd_link_candidates(fd_id: int) -> list[dict]:
    """Return transactions that could potentially be linked to an FD based on date and amount."""
    conn = get_connection()
    fd = conn.execute("SELECT * FROM FixedDeposit WHERE fd_id = ?", (fd_id,)).fetchone()
    if not fd:
        conn.close()
        return []

    query = """
        SELECT transaction_id, transaction_date, transaction_type, amount,
               category, mode, description, balance_after
        FROM Transactions
        WHERE account_id = ?
    """
    params = [fd["account_id"]]

    if fd["start_date"]:
        query += " AND transaction_date >= date(?, '-15 day')"
        params.append(fd["start_date"])
    if fd["maturity_date"]:
        query += " AND transaction_date <= date(?, '+30 day')"
        params.append(fd["maturity_date"])

    fd_ref = (fd["fd_reference_no"] or "").strip()
    if fd_ref:
        query += " AND (description LIKE ? OR category = 'FD Interest')"
        params.append(f"%{fd_ref}%")
    else:
        query += " AND (amount = ? OR category = 'FD Interest')"
        params.append(fd["principal_amount"])

    query += " ORDER BY transaction_date DESC, transaction_id DESC LIMIT 200"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def auto_link_fd_records(person_id: int, financial_year: str | None = None) -> int:
    """Auto-link unlinked FD records to transactions based on FD reference number. Returns count of linked records."""
    conn = get_connection()
    query = "SELECT * FROM FixedDeposit WHERE person_id = ? AND linked_transaction_id IS NULL"
    params = [person_id]
    if financial_year:
        start_year = int(financial_year.split("-")[0])
        query += " AND start_date BETWEEN ? AND ?"
        params.extend([f"{start_year}-04-01", f"{start_year+1}-03-31"])

    fds = conn.execute(query, params).fetchall()
    linked = 0
    for fd in fds:
        fd_ref = (fd["fd_reference_no"] or "").strip()
        if not fd_ref:
            continue
        txn = conn.execute(
            """
            SELECT transaction_id
            FROM Transactions
            WHERE account_id = ?
              AND description LIKE ?
            ORDER BY transaction_date DESC, transaction_id DESC
            LIMIT 1
            """,
            (fd["account_id"], f"%{fd_ref}%"),
        ).fetchone()
        if txn:
            conn.execute(
                "UPDATE FixedDeposit SET linked_transaction_id = ? WHERE fd_id = ?",
                (txn["transaction_id"], fd["fd_id"]),
            )
            linked += 1

    conn.commit()
    conn.close()
    return linked


def _extract_actual_fd_no(description: str, reference_no: str | None = None) -> str | None:
    text = (description or "").upper()
    if reference_no and "/" in reference_no:
        return reference_no.strip().upper()[:50]

    patterns = [
        r"\b(\d{10,}/\d+)\b",  # e.g. 4522030012104165/1
        r"\bFD\s*(?:NO|NUMBER|A/C|ACCOUNT)?\s*[:\-]?\s*([A-Z0-9\-/]{6,})\b",
        r"\bTD\s*(?:NO|NUMBER|A/C|ACCOUNT)?\s*[:\-]?\s*([A-Z0-9\-/]{6,})\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return m.group(1).strip(" -/").upper()[:50]
    return None


def apply_statement_redemption_event(account_id: int, person_id: int,
                                     transaction_id: int, transaction_date: str,
                                     amount: float, description: str,
                                     reference_no: str | None = None) -> int:
    """Maturity linking for statement redemption credits.

    Priority order:
    1) Match by actual FD no found in narration (e.g. 452203.../1).
    2) Fallback to principal-amount nearest match for redemption-principal rows.
    3) If still not found, create placeholder FD with start_date NULL.

    Returns fd_id if an FD was updated/created, else 0.
    """
    text = (description or "").upper()
    if not text:
        return 0

    is_auto_redeem = any(k in text for k in [
        "AUTO REDEEM", "FD CR", "PAT CR", "REDEMPTION", "REDEEMED", "MATURITY", "MATURED"
    ])
    if not is_auto_redeem:
        return 0

    is_interest_only = ("INT AUTO REDEEM" in text) and ("PRINC AND INT AUTO REDEEM" not in text)
    is_principal_redemption = ("PRINC AND INT AUTO REDEEM" in text) or not is_interest_only
    fd_no = _extract_actual_fd_no(description, reference_no)

    conn = get_connection()
    tx_row = conn.execute(
        "SELECT 1 FROM Transactions WHERE transaction_id = ?",
        (transaction_id,),
    ).fetchone()
    tx_exists = tx_row is not None
    chosen = None

    if fd_no:
        chosen = conn.execute(
            """
            SELECT fd_id, principal_amount, fd_reference_no, status,
                   start_date, actual_interest_amount,
                   source_transaction_id, linked_transaction_id
            FROM FixedDeposit
            WHERE account_id = ?
              AND person_id = ?
              AND UPPER(COALESCE(fd_reference_no, '')) = ?
            ORDER BY CASE status WHEN 'Active' THEN 0 WHEN 'Pending Details' THEN 1 WHEN 'Matured' THEN 2 ELSE 3 END,
                     fd_id DESC
            LIMIT 1
            """,
            (account_id, person_id, fd_no),
        ).fetchone()

    if fd_no and chosen is not None and is_principal_redemption and not chosen["start_date"]:
        placeholder = chosen
        candidates = conn.execute(
            """
            SELECT fd_id, principal_amount, start_date, status,
                   fd_reference_no, actual_interest_amount,
                   source_transaction_id, linked_transaction_id
            FROM FixedDeposit
            WHERE account_id = ?
              AND person_id = ?
              AND status IN ('Active', 'Pending Details')
              AND start_date IS NOT NULL
              AND (fd_reference_no IS NULL OR UPPER(fd_reference_no) != ?)
            ORDER BY fd_id DESC
            """,
            (account_id, person_id, fd_no),
        ).fetchall()

        if candidates:
            def _score(row):
                principal = float(row["principal_amount"] or 0)
                diff = abs(principal - float(amount or 0))
                return (diff, row["start_date"], row["fd_id"])

            best = min(candidates, key=_score)
            principal = float(best["principal_amount"] or 0)
            diff = abs(principal - float(amount or 0))
            if principal > 0 and diff <= max(1000.0, 0.2 * principal):
                # Merge placeholder interest data into the real FD and remove placeholder if safe.
                updates = ["fd_reference_no = ?", "status = 'Matured'", "maturity_date = COALESCE(maturity_date, ?)"]
                params = [fd_no, transaction_date]

                if placeholder["actual_interest_amount"] and not best["actual_interest_amount"]:
                    updates.append("actual_interest_amount = ?")
                    params.append(placeholder["actual_interest_amount"])

                if not best["source_transaction_id"] and placeholder["source_transaction_id"]:
                    updates.append("source_transaction_id = ?")
                    params.append(placeholder["source_transaction_id"])

                if not best["linked_transaction_id"] and placeholder["linked_transaction_id"]:
                    updates.append("linked_transaction_id = ?")
                    params.append(placeholder["linked_transaction_id"])

                params.append(best["fd_id"])
                conn.execute(
                    f"UPDATE FixedDeposit SET {', '.join(updates)} WHERE fd_id = ?",
                    params,
                )

                ref_row = conn.execute(
                    "SELECT 1 FROM FDInterestRecord WHERE fd_id = ?",
                    (placeholder["fd_id"],),
                ).fetchone()
                if not ref_row:
                    conn.execute("DELETE FROM FixedDeposit WHERE fd_id = ?", (placeholder["fd_id"],))
                conn.commit()
                chosen = best

    if chosen is None and is_principal_redemption:
        rows = conn.execute(
            """
            SELECT fd_id, principal_amount, fd_reference_no, status
            FROM FixedDeposit
            WHERE account_id = ?
              AND person_id = ?
              AND status IN ('Active', 'Pending Details')
              AND (start_date IS NULL OR start_date <= ?)
            ORDER BY fd_id DESC
            """,
            (account_id, person_id, transaction_date),
        ).fetchall()
        if rows:
            scored = sorted(
                rows,
                key=lambda r: (abs(float(r["principal_amount"] or 0) - float(amount or 0)), r["fd_id"]),
            )
            chosen = scored[0]

    if chosen is None:
        if is_interest_only and not fd_no:
            conn.close()
            return 0
        principal = 0.0 if is_interest_only else float(amount or 0)
        interest = float(amount or 0) if is_interest_only else None
        cur = conn.execute(
            """
            INSERT INTO FixedDeposit
                (account_id, person_id, principal_amount, start_date,
                 fd_reference_no, tenure_years, tenure_months, tenure_days,
                 interest_rate, compounding_type, maturity_date,
                 maturity_amount, maturity_amount_formula, maturity_amount_bank,
                 maturity_calc_method, expected_interest_amount, actual_interest_amount,
                 linked_transaction_id, source_transaction_id, status, source_description)
            VALUES (?, ?, ?, ?, ?, 0, NULL, 0, NULL, NULL, ?, NULL, NULL, NULL,
                    'Bank Style', NULL, ?, ?, ?, 'Matured', ?)
            """,
            (
                account_id,
                person_id,
                principal,
                None,
                fd_no,
                transaction_date,
                interest,
                (transaction_id if tx_exists else None),
                (transaction_id if tx_exists else None),
                (description or "")[:500],
            ),
        )
        conn.commit()
        new_id = int(cur.lastrowid)
        conn.close()
        return new_id

    fd_id = int(chosen["fd_id"])
    updates = ["status = 'Matured'", "maturity_date = COALESCE(maturity_date, ?)"]
    params: list = [transaction_date]

    if tx_exists:
        updates.append("source_transaction_id = COALESCE(source_transaction_id, ?)")
        params.append(transaction_id)

    # Keep principal transaction linked; interest transaction shouldn't overwrite that.
    if not is_interest_only and tx_exists:
        updates.append("linked_transaction_id = ?")
        params.append(transaction_id)

    if fd_no:
        updates.append("fd_reference_no = ?")
        params.append(fd_no)

    if is_interest_only:
        updates.append("actual_interest_amount = COALESCE(?, actual_interest_amount)")
        params.append(float(amount or 0))
    else:
        current_principal = float(chosen["principal_amount"] or 0)
        if current_principal <= 0 and float(amount or 0) > 0:
            updates.append("principal_amount = ?")
            params.append(float(amount or 0))
        if current_principal > 0 and float(amount or 0) > current_principal:
            updates.append("actual_interest_amount = COALESCE(?, actual_interest_amount)")
            params.append(float(amount or 0) - current_principal)

    params.append(fd_id)
    conn.execute(f"UPDATE FixedDeposit SET {', '.join(updates)} WHERE fd_id = ?", params)
    conn.commit()
    conn.close()
    return fd_id


def delete_fd(fd_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM FixedDeposit WHERE fd_id = ?", (fd_id,))
    conn.commit()
    conn.close()
