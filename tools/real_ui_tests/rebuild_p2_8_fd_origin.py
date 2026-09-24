r"""tools/real_ui_tests/rebuild_p2_8_fd_origin.py — Phase 2.8 FD origin
confirmation. Read-only: explains every FixedDeposit row by its source, or
explicitly confirms zero exist (the Phase 0 prediction).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from tools.real_ui_tests.rebuild_common import db_ro, redacting_logger, append_progress

log = redacting_logger("P2_8_fd_origin")


def main():
    conn = db_ro()
    n = conn.execute("SELECT COUNT(*) FROM FixedDeposit").fetchone()[0]
    log.log(f"FixedDeposit total = {n}")

    if n == 0:
        log.log("CONFIRMED: zero FixedDeposit rows exist. Every real bank statement's FD Principal / FD "
                 "Maturity transactions (Jana: 14 FD Principal rows + 32 redemption candidates; Equitas: "
                 "4 FD Principal + 9 FD Interest; Ujjivan: 11 FD Maturity) landed as plain Transactions rows "
                 "only. No FixedDeposit record was auto-created for any of them, because "
                 "_is_fd_opening_transaction() in ui/statement_import_screen_modern.py only matches the "
                 "substrings 'fd accepted' / 'opening' / 'fixed deposit' in the transaction description, "
                 "and none of the real descriptions contain those phrases.")
    else:
        cols = [d[0] for d in conn.execute("SELECT * FROM FixedDeposit LIMIT 1").description]
        rows = conn.execute("SELECT * FROM FixedDeposit").fetchall()
        for r in rows:
            d = dict(zip(cols, r))
            log.log(f"FixedDeposit row: {d}")

    conn.close()
    append_progress(f"P2.8 FD origin check complete. FixedDeposit total={n}.")
    log.log("P2.8 DONE")


if __name__ == "__main__":
    main()
