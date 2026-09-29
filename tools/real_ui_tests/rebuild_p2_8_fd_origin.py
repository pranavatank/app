r"""tools/real_ui_tests/rebuild_p2_8_fd_origin.py — Phase 2.8 FD origin
confirmation. Read-only: explains every FixedDeposit row by its source.
Checks expected vs actual FD-opening transaction matching.
"""
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from tools.real_ui_tests.rebuild_common import db_ro, redacting_logger, append_progress

log = redacting_logger("P2_8_fd_origin")


def mask_digits_6_plus(text):
    """Mask digit runs of 6+ characters to show only last 4."""
    return re.sub(r'\d{6,}', lambda m: '*' * (len(m.group(0)) - 4) + m.group(0)[-4:], text)


def main():
    # Create a minimal QApplication to avoid issues with importing ui code
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])

    # Import the actual _TransactionImportWorker to use its regex-based FD detection
    from ui.statement_import_screen_modern import _TransactionImportWorker

    # Create an instance with empty/None arguments to access _is_fd_opening_transaction
    worker = _TransactionImportWorker(None, None, [], [], '', '', '', [])

    conn = db_ro()

    # 1. Log FD status summary
    fd_status_query = "SELECT account_id, status, COUNT(*) FROM FixedDeposit GROUP BY account_id, status"
    fd_status_rows = conn.execute(fd_status_query).fetchall()
    log.log("FixedDeposit status summary:")
    if fd_status_rows:
        for account_id, status, cnt in fd_status_rows:
            log.log(f"  account_id={account_id} status={status} count={cnt}")
    else:
        log.log("  (no FixedDeposit rows)")

    # Get all account_ids from Transactions
    txn_account_ids = set()
    rows = conn.execute("SELECT DISTINCT account_id FROM Transactions ORDER BY account_id").fetchall()
    for (acc_id,) in rows:
        txn_account_ids.add(acc_id)
    log.log(f"Accounts with Transactions: {sorted(txn_account_ids)}")

    # 2. For each account: compute expected vs actual FD-opening transaction ids
    results = {}
    for account_id in sorted(txn_account_ids):
        # Get transaction data for this account
        txn_rows = conn.execute(
            "SELECT transaction_id, transaction_type, category, description, amount FROM Transactions WHERE account_id=?",
            (account_id,)
        ).fetchall()

        txn_cols = ["transaction_id", "transaction_type", "category", "description", "amount"]

        # Compute expected FD-opening transaction ids using the actual worker method
        expected_ids = set()
        for txn in txn_rows:
            txn_dict = dict(zip(txn_cols, txn))
            if worker._is_fd_opening_transaction(txn_dict):
                expected_ids.add(txn_dict["transaction_id"])

        # 3. Get actual FD-opening transaction ids (from FixedDeposit.source_transaction_id)
        actual_rows = conn.execute(
            "SELECT source_transaction_id FROM FixedDeposit WHERE account_id=? AND source_transaction_id IS NOT NULL AND start_date IS NOT NULL",
            (account_id,)
        ).fetchall()
        actual_ids = set(row[0] for row in actual_rows)

        expected_n = len(expected_ids)
        actual_n = len(actual_ids)
        set_equal = expected_ids == actual_ids

        results[account_id] = {
            "expected_n": expected_n,
            "actual_n": actual_n,
            "set_equal": set_equal,
            "expected_ids": expected_ids,
            "actual_ids": actual_ids,
        }

        # 4. Log per account
        status_str = "OK" if set_equal else "PRE-FIX IMPORT or FINDING"
        log.log(f"account_id={account_id}: expected={expected_n}, actual={actual_n}, match={set_equal} [{status_str}]")

    # 5. For each FD with a source transaction: verify data matches
    fd_cols_query = "SELECT * FROM FixedDeposit LIMIT 1"
    cols = [d[0] for d in conn.execute(fd_cols_query).description]

    fds = conn.execute(
        "SELECT * FROM FixedDeposit WHERE source_transaction_id IS NOT NULL"
    ).fetchall()

    if fds:
        log.log("FixedDeposit rows with source_transaction_id:")
        for fd_row in fds:
            fd_dict = dict(zip(cols, fd_row))
            fd_id = fd_dict.get("fd_id")
            source_txn_id = fd_dict.get("source_transaction_id")
            account_id = fd_dict.get("account_id")
            principal = fd_dict.get("principal_amount")
            start_date = fd_dict.get("start_date")
            status = fd_dict.get("status")
            fd_ref_no = fd_dict.get("fd_reference_no")

            # Mask fd_reference_no to last 4 digits
            fd_ref_masked = mask_digits_6_plus(str(fd_ref_no)) if fd_ref_no else "None"

            # Join to Transactions
            txn_data = conn.execute(
                "SELECT amount, transaction_date, account_id FROM Transactions WHERE transaction_id=?",
                (source_txn_id,)
            ).fetchone()

            if txn_data:
                txn_amount, txn_date, txn_account_id = txn_data
                amt_match = (float(txn_amount) == float(principal))
                date_match = (str(txn_date) == str(start_date))
                acct_match = (txn_account_id == account_id)

                log.log(f"  FD fd_id={fd_id}: ref={fd_ref_masked} status={status} "
                       f"amount_match={amt_match} date_match={date_match} account_match={acct_match}")
            else:
                log.log(f"  FD fd_id={fd_id}: ref={fd_ref_masked} status={status} "
                       f"ERROR: source_transaction_id {source_txn_id} not found in Transactions")

    # 6. List FDs with NULL source_transaction_id
    null_source_fds = conn.execute(
        "SELECT fd_id, status, linked_transaction_id FROM FixedDeposit WHERE source_transaction_id IS NULL"
    ).fetchall()

    if null_source_fds:
        log.log("FixedDeposit rows with NULL source_transaction_id:")
        for fd_id, status, linked_txn_id in null_source_fds:
            log.log(f"  FD fd_id={fd_id}: status={status} linked_transaction_id={linked_txn_id}")
    else:
        log.log("No FixedDeposit rows with NULL source_transaction_id")

    conn.close()

    # Summary to PROGRESS.md
    summary_lines = []
    for account_id in sorted(results.keys()):
        r = results[account_id]
        status = "OK" if r["set_equal"] else "PRE-FIX"
        summary_lines.append(f"account_id={account_id}: expected={r['expected_n']}, actual={r['actual_n']} [{status}]")

    summary_text = "; ".join(summary_lines) if summary_lines else "no accounts with Transactions"
    append_progress(f"P2.8 FD origin: {summary_text}")
    log.log("P2.8 DONE")


if __name__ == "__main__":
    main()
