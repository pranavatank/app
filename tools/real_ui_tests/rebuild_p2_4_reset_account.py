r"""tools/real_ui_tests/rebuild_p2_4_reset_account.py — Reset an account (delete FDs and transactions).

Usage: python run_on_scratch.py rebuild_p2_4_reset_account.py --bank <name> --expect-count N

Read-only mode: tests via --help; does NOT write to real DB or run without run_on_scratch.py.
"""
import sys
import sqlite3
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.real_ui_tests.rebuild_common import (
    RUIH_DIR, REAL_DB_PATH, require_scratch, redacting_logger, snapshot_db, append_progress,
    fingerprint_real_db, diff_fingerprints,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", required=True)
    ap.add_argument("--expect-count", type=int, required=True)
    ap.add_argument("--real", action="store_true")
    ap.add_argument("--confirm-account-id", type=int)
    args = ap.parse_args()

    bank = args.bank
    expect_count = args.expect_count

    import config

    if args.real:
        if Path(config.DB_PATH).resolve() != REAL_DB_PATH.resolve():
            print("STOP: --real must not run under run_on_scratch")
            sys.exit(2)
        if args.confirm_account_id is None:
            print("STOP: --real requires --confirm-account-id")
            sys.exit(2)
    else:
        require_scratch()

    DB_PATH = config.DB_PATH
    log = redacting_logger(f"P2_4_reset_{bank.replace(' ', '_')}")

    from models.fixed_deposit import delete_fd
    from models.transaction import delete_transactions_by_ids

    if args.real:
        log.log("REAL DB MODE")
        fp_before = fingerprint_real_db(REAL_DB_PATH)

    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)

    account_row = conn.execute(
        "SELECT account_id FROM BankAccount WHERE bank_name LIKE ? ORDER BY account_id LIMIT 1",
        (f"%{bank.split()[0]}%",),
    ).fetchone()

    if account_row is None:
        log.log(f"STOP: no BankAccount row matching bank={bank!r}")
        conn.close()
        sys.exit(2)

    account_id = account_row[0]

    if args.real and account_id != args.confirm_account_id:
        log.log(f"STOP: account_id {account_id} != confirmed {args.confirm_account_id}")
        sys.exit(2)

    tx_rows = conn.execute(
        "SELECT transaction_id FROM Transactions WHERE account_id=? ORDER BY transaction_id",
        (account_id,),
    ).fetchall()
    tx_ids = [r[0] for r in tx_rows]
    tx_count = len(tx_ids)

    if tx_count != expect_count:
        log.log(f"STOP: transaction count {tx_count} != expected {expect_count}")
        conn.close()
        sys.exit(2)

    fd_rows = conn.execute(
        "SELECT fd_id FROM FixedDeposit WHERE account_id=? ORDER BY fd_id",
        (account_id,),
    ).fetchall()
    fd_ids = [r[0] for r in fd_rows]

    other_account_tx_ids = set()
    other_account_fd_ids = set()
    other_rows = conn.execute(
        "SELECT DISTINCT account_id FROM BankAccount WHERE account_id != ? ORDER BY account_id",
        (account_id,),
    ).fetchall()
    for (other_id,) in other_rows:
        other_tx = conn.execute(
            "SELECT transaction_id FROM Transactions WHERE account_id=?",
            (other_id,),
        ).fetchall()
        other_account_tx_ids.update(r[0] for r in other_tx)

        other_fd = conn.execute(
            "SELECT fd_id FROM FixedDeposit WHERE account_id=?",
            (other_id,),
        ).fetchall()
        other_account_fd_ids.update(r[0] for r in other_fd)

    is_internal_before = set()
    is_internal_rows = conn.execute(
        "SELECT transaction_id FROM Transactions WHERE is_internal_transfer=1 AND account_id != ?",
        (account_id,),
    ).fetchall()
    is_internal_before = set(r[0] for r in is_internal_rows)

    conn.close()

    log.log(f"account_id={account_id} tx_count={tx_count} fd_count={len(fd_ids)}")
    log.log(f"Deleting {len(fd_ids)} FDs and {len(tx_ids)} transactions")

    if not args.real:
        snapshot_db(f"pre_reset_{bank}")

    for fd_id in fd_ids:
        delete_fd(fd_id)
    if tx_ids:
        delete_transactions_by_ids(tx_ids)

    if args.real:
        from services import engines
        engines.balance_engine.recalculate_account_balance(account_id)

    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)

    verify_tx_count = conn.execute(
        "SELECT COUNT(*) FROM Transactions WHERE account_id=?",
        (account_id,),
    ).fetchone()[0]
    verify_fd_count = conn.execute(
        "SELECT COUNT(*) FROM FixedDeposit WHERE account_id=?",
        (account_id,),
    ).fetchone()[0]

    log.log(f"After deletion: tx_count={verify_tx_count} fd_count={verify_fd_count}")

    if verify_tx_count != 0 or verify_fd_count != 0:
        log.log(f"STOP: deletion incomplete tx={verify_tx_count} fd={verify_fd_count}")
        conn.close()
        sys.exit(2)

    verify_other_tx = set()
    verify_other_fd = set()
    verify_rows = conn.execute(
        "SELECT DISTINCT account_id FROM BankAccount WHERE account_id != ? ORDER BY account_id",
        (account_id,),
    ).fetchall()
    for (other_id,) in verify_rows:
        verify_tx = conn.execute(
            "SELECT transaction_id FROM Transactions WHERE account_id=?",
            (other_id,),
        ).fetchall()
        verify_other_tx.update(r[0] for r in verify_tx)

        verify_fd = conn.execute(
            "SELECT fd_id FROM FixedDeposit WHERE account_id=?",
            (other_id,),
        ).fetchall()
        verify_other_fd.update(r[0] for r in verify_fd)

    if verify_other_tx != other_account_tx_ids or verify_other_fd != other_account_fd_ids:
        log.log(f"WARNING: other accounts' tx/fd sets changed unexpectedly")

    is_internal_after = set()
    is_internal_rows_after = conn.execute(
        "SELECT transaction_id FROM Transactions WHERE is_internal_transfer=1 AND account_id != ?",
        (account_id,),
    ).fetchall()
    is_internal_after = set(r[0] for r in is_internal_rows_after)

    is_internal_diff = is_internal_before.symmetric_difference(is_internal_after)
    if is_internal_diff:
        log.log(f"is_internal_transfer changed: {sorted(is_internal_diff)}")
    else:
        log.log(f"is_internal_transfer unchanged (expected)")

    conn.close()

    if args.real:
        fp_after = fingerprint_real_db(REAL_DB_PATH)
        allowed = {"Transactions","FixedDeposit","FDInterestRecord","BankAccount","SavingsInterestRecord"}
        changed = diff_fingerprints(fp_before, fp_after)
        if changed and not changed.issubset(allowed):
            unexpected = changed - allowed
            log.log(f"STOP: unexpected tables changed: {unexpected}")
            sys.exit(2)
        log.log(f"Real DB fingerprint OK: {changed if changed else 'no changes'}")

    append_progress(f"P2.4 account reset complete for {bank}. {tx_count} transactions and {len(fd_ids)} FDs deleted.")
    log.log("P2.4 reset DONE")


if __name__ == "__main__":
    main()
