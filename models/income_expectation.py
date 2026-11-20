"""
models/income_expectation.py — Income expectation tracking
"""

from collections import defaultdict

from core.database import get_connection
from config import fy_date_range

def add_income_expectation(person_id, account_id, income_type, expected_amount,
                          expected_date, frequency, financial_year, notes=None):
    """Add new income expectation(s). For recurring, creates multiple records."""
    conn = get_connection()
    try:
        if frequency == "Monthly":
            # Create 12 records for the financial year
            from datetime import datetime
            from dateutil.relativedelta import relativedelta
            from config import fy_date_range

            fy_start, fy_end = fy_date_range(financial_year)
            day_of_month = int(expected_date)  # expected_date is now just the day number

            current_date = fy_start.replace(day=min(day_of_month, 28))  # Start with FY start month
            records_created = []

            for month_offset in range(12):
                month_date = current_date + relativedelta(months=month_offset)
                # Handle day overflow (e.g., 31st in Feb)
                try:
                    actual_date = month_date.replace(day=day_of_month)
                except ValueError:
                    # Day doesn't exist in this month, use last day
                    actual_date = month_date.replace(day=1) + relativedelta(months=1, days=-1)

                if actual_date > fy_end:
                    break

                conn.execute("""
                    INSERT INTO IncomeExpectation
                    (person_id, account_id, income_type, expected_amount, expected_date,
                     frequency, financial_year, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (person_id, account_id, income_type, expected_amount, actual_date.isoformat(),
                      frequency, financial_year, notes))
                records_created.append(conn.execute("SELECT last_insert_rowid()").fetchone()[0])

            conn.commit()
            return records_created

        elif frequency == "Quarterly":
            # Create 4 records
            from datetime import datetime
            from dateutil.relativedelta import relativedelta
            from config import fy_date_range

            fy_start, fy_end = fy_date_range(financial_year)
            day_of_month = int(expected_date)
            current_date = fy_start.replace(day=min(day_of_month, 28))
            records_created = []

            for quarter in range(4):
                month_date = current_date + relativedelta(months=quarter * 3)
                try:
                    actual_date = month_date.replace(day=day_of_month)
                except ValueError:
                    actual_date = month_date.replace(day=1) + relativedelta(months=1, days=-1)

                if actual_date > fy_end:
                    break

                conn.execute("""
                    INSERT INTO IncomeExpectation
                    (person_id, account_id, income_type, expected_amount, expected_date,
                     frequency, financial_year, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (person_id, account_id, income_type, expected_amount, actual_date.isoformat(),
                      frequency, financial_year, notes))
                records_created.append(conn.execute("SELECT last_insert_rowid()").fetchone()[0])

            conn.commit()
            return records_created

        elif frequency == "Half-Yearly":
            # Create 2 records
            from datetime import datetime
            from dateutil.relativedelta import relativedelta
            from config import fy_date_range

            fy_start, fy_end = fy_date_range(financial_year)
            day_of_month = int(expected_date)
            current_date = fy_start.replace(day=min(day_of_month, 28))
            records_created = []

            for half in range(2):
                month_date = current_date + relativedelta(months=half * 6)
                try:
                    actual_date = month_date.replace(day=day_of_month)
                except ValueError:
                    actual_date = month_date.replace(day=1) + relativedelta(months=1, days=-1)

                if actual_date > fy_end:
                    break

                conn.execute("""
                    INSERT INTO IncomeExpectation
                    (person_id, account_id, income_type, expected_amount, expected_date,
                     frequency, financial_year, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (person_id, account_id, income_type, expected_amount, actual_date.isoformat(),
                      frequency, financial_year, notes))
                records_created.append(conn.execute("SELECT last_insert_rowid()").fetchone()[0])

            conn.commit()
            return records_created

        else:
            # One-Time or Yearly - single record with full date
            conn.execute("""
                INSERT INTO IncomeExpectation
                (person_id, account_id, income_type, expected_amount, expected_date,
                 frequency, financial_year, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (person_id, account_id, income_type, expected_amount, expected_date,
                  frequency, financial_year, notes))
            conn.commit()
            return [conn.execute("SELECT last_insert_rowid()").fetchone()[0]]
    finally:
        conn.close()

def get_income_expectations(person_id=None, financial_year=None, income_type=None):
    """Get income expectations with joined data."""
    conn = get_connection()
    try:
        query = """
            SELECT
                ie.*,
                p.full_name as person_name,
                ba.bank_name,
                COALESCE(NULLIF(b.nickname, ''), ba.bank_name) AS bank_display_name,
                ba.account_type,
                t.amount as actual_amount,
                t.transaction_date as actual_date
            FROM IncomeExpectation ie
            JOIN Person p ON ie.person_id = p.person_id
            JOIN BankAccount ba ON ie.account_id = ba.account_id
            LEFT JOIN Bank b ON b.bank_id = (
                SELECT bank_id FROM Bank WHERE lower(bank_name) = lower(ba.bank_name)
                ORDER BY bank_id LIMIT 1
            )
            LEFT JOIN Transactions t ON ie.actual_transaction_id = t.transaction_id
            WHERE 1=1
        """
        params = []
        if person_id:
            query += " AND ie.person_id = ?"
            params.append(person_id)
        if financial_year:
            query += " AND ie.financial_year = ?"
            params.append(financial_year)
        if income_type:
            query += " AND ie.income_type = ?"
            params.append(income_type)
        query += " ORDER BY ie.expected_date DESC"

        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def update_income_expectation(expectation_id, expected_amount=None, expected_date=None,
                              frequency=None, notes=None):
    """Update income expectation."""
    conn = get_connection()
    try:
        updates = []
        params = []

        if expected_amount is not None:
            updates.append("expected_amount = ?")
            params.append(expected_amount)
        if expected_date is not None:
            updates.append("expected_date = ?")
            params.append(expected_date)
        if frequency is not None:
            updates.append("frequency = ?")
            params.append(frequency)
        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)

        if updates:
            params.append(expectation_id)
            conn.execute(f"""
                UPDATE IncomeExpectation
                SET {', '.join(updates)}
                WHERE expectation_id = ?
            """, params)
            conn.commit()
    finally:
        conn.close()

def link_actual_transaction(expectation_id, transaction_id):
    """Link one external credit from the expected account and financial year."""
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        expectation = conn.execute(
            "SELECT * FROM IncomeExpectation WHERE expectation_id = ?", (expectation_id,),
        ).fetchone()
        if expectation is None:
            raise ValueError("This expectation no longer exists.")
        start, end = fy_date_range(expectation["financial_year"])
        eligible = conn.execute("""
            SELECT 1 FROM Transactions t
            WHERE t.transaction_id = ? AND t.person_id = ? AND t.account_id = ?
              AND t.transaction_type = 'Income' AND t.amount > 0
              AND COALESCE(t.is_internal_transfer, 0) = 0
              AND COALESCE(t.category, '') NOT IN ('Internal Transfer', 'FD Maturity')
              AND t.transaction_date BETWEEN ? AND ?
              AND NOT EXISTS (
                  SELECT 1 FROM IncomeExpectation e WHERE e.actual_transaction_id = t.transaction_id
                    AND e.expectation_id <> ?
              )
        """, (transaction_id, expectation["person_id"], expectation["account_id"],
              start.isoformat(), end.isoformat(), expectation_id)).fetchone()
        if not eligible:
            raise ValueError("Choose an unlinked income credit from this account and financial year.")
        conn.execute("""
            UPDATE IncomeExpectation
            SET actual_transaction_id = ?
            WHERE expectation_id = ?
        """, (transaction_id, expectation_id))
        conn.commit()
    finally:
        conn.close()

def unlink_actual_transaction(expectation_id):
    """Unlink actual transaction from expectation."""
    conn = get_connection()
    try:
        conn.execute("""
            UPDATE IncomeExpectation
            SET actual_transaction_id = NULL
            WHERE expectation_id = ?
        """, (expectation_id,))
        conn.commit()
    finally:
        conn.close()

def delete_income_expectation(expectation_id):
    """Delete income expectation."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM IncomeExpectation WHERE expectation_id = ?", (expectation_id,))
        conn.commit()
    finally:
        conn.close()

def auto_link_income_expectations(person_id, account_id, financial_year):
    """Match an unambiguous, categorized credit in the expected month."""
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        expectations = conn.execute("""
            SELECT expectation_id, expected_date, income_type, expected_amount
            FROM IncomeExpectation
            WHERE person_id = ? AND account_id = ? AND financial_year = ?
            AND actual_transaction_id IS NULL
            ORDER BY expected_date
        """, (person_id, account_id, financial_year)).fetchall()

        if not expectations:
            return 0

        fy_start, fy_end = fy_date_range(financial_year)

        transactions = conn.execute("""
            SELECT transaction_id, transaction_date, amount, category
            FROM Transactions
            WHERE person_id = ? AND account_id = ?
            AND transaction_type = 'Income' AND amount > 0
            AND COALESCE(is_internal_transfer, 0) = 0
            AND COALESCE(category, '') NOT IN ('Internal Transfer', 'FD Maturity')
            AND transaction_date BETWEEN ? AND ?
            AND transaction_id NOT IN (
                SELECT actual_transaction_id
                FROM IncomeExpectation
                WHERE actual_transaction_id IS NOT NULL
            )
            ORDER BY transaction_date
        """, (person_id, account_id, fy_start.isoformat(), fy_end.isoformat())).fetchall()

        if not transactions:
            return 0

        from datetime import datetime

        available = [
            {
                "transaction_id": t["transaction_id"],
                "date": datetime.strptime(t["transaction_date"], "%Y-%m-%d").date(),
                "amount": t["amount"],
                "category": (t["category"] or "").casefold(),
            }
            for t in transactions
        ]

        proposals = defaultdict(list)

        for exp in expectations:
            exp_date = datetime.strptime(exp["expected_date"], "%Y-%m-%d").date()
            exp_amount = exp["expected_amount"]
            exp_day = exp_date.day
            income_type = exp["income_type"].casefold()
            categories = {
                "interest": {"fd interest", "savings interest", "interest"},
                "rent": {"rental income", "rent"},
                "business": {"business income", "business"},
                "freelance": {"professional fees", "freelance"},
            }.get(income_type, {income_type})

            # Candidates: same month+year, amount within 50 % of expected
            candidates = [
                t for t in available
                if t["date"].month == exp_date.month
                and t["date"].year == exp_date.year
                and t["category"] in categories
                and abs(t["amount"] - exp_amount) <= exp_amount * 0.50
            ]

            if not candidates:
                continue

            # Score: primary = amount proximity (ratio), secondary = date proximity (days)
            def score(t):
                amount_score = abs(t["amount"] - exp_amount) / max(exp_amount, 1)
                date_score = abs(t["date"].day - exp_day) / 31.0
                return (amount_score, date_score)

            candidates.sort(key=score)
            best = candidates[0]
            if len(candidates) > 1 and score(best) == score(candidates[1]):
                continue
            proposals[best["transaction_id"]].append((score(best), exp["expectation_id"]))

        linked_count = 0
        for transaction_id, matches in proposals.items():
            matches.sort()
            if len(matches) > 1 and matches[0][0] == matches[1][0]:
                continue
            conn.execute("""
                UPDATE IncomeExpectation
                SET actual_transaction_id = ?
                WHERE expectation_id = ?
            """, (transaction_id, matches[0][1]))
            linked_count += 1

        conn.commit()
        return linked_count
    finally:
        conn.close()
