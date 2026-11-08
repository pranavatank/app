"""Read-only FD provenance checks for a fresh statement rebuild."""
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from tests.native.rebuild_preflight import finite_money


def _redemption_kind(txn):
    """The event kinds accepted by apply_statement_redemption_event."""
    if txn.get("transaction_type") != "Income":
        return None
    text = (txn.get("description") or "").upper()
    if not any(term in text for term in (
        "AUTO REDEEM", "FD CR", "PAT CR", "REDEMPTION", "REDEEMED", "MATURITY", "MATURED",
    )):
        return None
    return "interest" if "INT AUTO REDEEM" in text and "PRINC AND INT AUTO REDEEM" not in text else "principal"


def validate_fd_provenance(transactions, fds, is_opening, extract_reference):
    """Return counts and discrepancies without touching a database or GUI.

    Callers supply the production opening detector and redemption-reference
    extractor. Unknown opening dates stay unknown for redemption placeholders.
    """
    txns = {txn["transaction_id"]: txn for txn in transactions}
    expected = {tid for tid, txn in txns.items() if is_opening(txn)}
    opening_links = Counter()
    source_links = Counter()
    failures = []
    counts = {"opening": 0, "redemption_only": 0}

    def money_equal(left, right):
        return abs(left - right) <= Decimal("0.01")

    def reference(txn):
        return extract_reference(txn.get("description") or "", txn.get("reference_no"))

    def same_reference(left, right):
        # Production matches both a numbered FD and its base number.
        return (left or "").split("/")[0].strip().upper() == (right or "").split("/")[0].strip().upper()

    for fd in fds:
        fd_id = fd["fd_id"]
        source_id = fd.get("source_transaction_id")
        if source_id is not None:
            source_links[source_id] += 1
        source = txns.get(source_id)
        try:
            if source is None:
                raise ValueError("source transaction is missing")
            for field in ("account_id", "person_id"):
                if fd.get(field) != source.get(field):
                    raise ValueError(f"source {field} differs")
            principal = finite_money(fd.get("principal_amount"), "principal")
            if principal < 0:
                raise ValueError("principal is negative")

            if fd.get("start_date") is not None:
                counts["opening"] += 1
                if source_id not in expected:
                    raise ValueError("dated FD source is not an opening debit")
                opening_links[source_id] += 1
                if fd["start_date"] != source.get("transaction_date"):
                    raise ValueError("opening date differs")
                if not money_equal(principal, finite_money(source.get("amount"), "opening amount")):
                    raise ValueError("opening principal differs")
                continue

            # A missing opening date never excuses an invalid opening link.
            counts["redemption_only"] += 1
            if source_id in expected or _redemption_kind(source) is None:
                raise ValueError("undated FD source is not a redemption credit")
            if fd.get("status") != "Matured":
                raise ValueError("redemption-only FD is not Matured")
            linked = txns.get(fd.get("linked_transaction_id"))
            if linked is None or _redemption_kind(linked) is None:
                raise ValueError("redemption credit link is missing or invalid")
            for txn in (source, linked):
                if any(fd.get(key) != txn.get(key) for key in ("account_id", "person_id")):
                    raise ValueError("redemption credit owner differs")
                if not same_reference(fd.get("fd_reference_no"), reference(txn)):
                    raise ValueError("redemption reference differs")
                if finite_money(txn.get("amount"), "redemption amount") < 0:
                    raise ValueError("redemption amount is negative")
            if fd.get("maturity_date") != source.get("transaction_date"):
                raise ValueError("redemption maturity date differs from first source credit")

            interest = finite_money(fd.get("actual_interest_amount") or 0, "actual interest")
            if interest < 0:
                raise ValueError("actual interest is negative")
            linked_amount = finite_money(linked.get("amount"), "linked credit amount")
            if _redemption_kind(linked) == "interest":
                if source_id != linked["transaction_id"] or principal != 0 or not money_equal(interest, linked_amount):
                    raise ValueError("interest-only placeholder amounts differ")
            else:
                if not (money_equal(linked_amount, principal) or money_equal(linked_amount, principal + interest)):
                    raise ValueError("redemption principal differs from linked credit")
                source_amount = finite_money(source.get("amount"), "source credit amount")
                if _redemption_kind(source) == "principal" and not (
                    money_equal(source_amount, principal) or money_equal(source_amount, principal + interest)
                ):
                    raise ValueError("redemption principal differs from source credit")
                # Interest can be a separate credit (including the first source)
                # or the excess in a later combined principal/interest credit.
                if interest:
                    separate = any(
                        _redemption_kind(txn) == "interest"
                        and all(fd.get(key) == txn.get(key) for key in ("account_id", "person_id"))
                        and bool(reference(txn))
                        and same_reference(fd.get("fd_reference_no"), reference(txn))
                        and money_equal(interest, finite_money(txn.get("amount"), "interest credit amount"))
                        for txn in transactions
                    )
                    combined = linked_amount > principal and money_equal(linked_amount - principal, interest)
                    if not (separate or combined):
                        raise ValueError("actual interest has no matching redemption credit")
        except ValueError as exc:
            failures.append(f"fd_id={fd_id}: {exc}")

    missing = expected - opening_links.keys()
    if missing:
        failures.append(f"missing opening FD source links: {sorted(missing)}")
    for source_id, count in source_links.items():
        if count > 1:
            failures.append(f"duplicate FD source transaction link: {source_id}")
    return counts, failures


def main():
    from PySide6.QtWidgets import QApplication
    from ui.statement_import_screen_modern import _TransactionImportWorker
    from models.fixed_deposit import _extract_actual_fd_no
    from tests.native.rebuild_common import db_ro, redacting_logger, append_progress

    app = QApplication.instance() or QApplication([])
    worker = _TransactionImportWorker(None, None, [], [], '', '', '', [])
    log = redacting_logger("P2_8_fd_origin")
    conn = db_ro()
    try:
        def records(table):
            cursor = conn.execute(f"SELECT * FROM {table}")
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

        counts, failures = validate_fd_provenance(
            records("Transactions"), records("FixedDeposit"),
            worker._is_fd_opening_transaction, _extract_actual_fd_no,
        )
    finally:
        conn.close()
    log.log(f"FD provenance counts: opening={counts['opening']}, redemption_only={counts['redemption_only']}")
    if failures:
        for failure in failures:
            log.log(f"FAIL: {failure}")
        raise AssertionError(f"FD origin verification failed with {len(failures)} discrepancy(s)")
    append_progress(f"P2.8 FD origin: opening={counts['opening']}, redemption_only={counts['redemption_only']} [OK]")
    log.log("P2.8 DONE")


if __name__ == "__main__":
    from tests.native.rebuild_common import run_logged
    run_logged(main, "P2_8_fd_origin_crash")
