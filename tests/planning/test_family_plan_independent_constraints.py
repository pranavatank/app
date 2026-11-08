"""Integrated independent acceptance for pooled family FD constraints."""
from datetime import date, datetime, timezone
import math
import pytest

from engines.family_fd_engine import build_family_plan
from engines.family_workbook import FamilyData
from engines.fd_rates import RateCard
from engines.official_bank_rates import BankRates, SavingsSlab


def _verified_bundle(bank: str, rate: float, as_of: date) -> BankRates:
    checked_at = datetime.now(timezone.utc).isoformat()
    quote = RateCard(
        id=f"synthetic-{bank.lower()}", bank=bank, min_days=365, max_days=365,
        rate=rate, customer="general", effective_from=as_of.isoformat(),
        checked_at=checked_at, source_url=f"https://rates.example.invalid/{bank.lower()}",
        min_amount=1_000, max_amount=500_000, verified=True, bank_insured=True,
    )
    return BankRates(
        bank, quote.source_url, checked_at, fd_rates=[quote],
        savings=[SavingsSlab(0, None, 1.0, "Synthetic flat rate")],
    )


def test_pooled_plan_reconciles_cash_caps_transfers_and_annual_income():
    as_of = date.today()
    current_fy_start = as_of.year if as_of.month >= 4 else as_of.year - 1
    # FamilyData income_by_fy uses integer FY start years, as populated by
    # family_workbook.fy_start and consumed by family_fd_engine.year_fractions.
    years = range(current_fy_start, current_fy_start + 3)
    baseline = {year: 1_190_000 for year in years}
    data = FamilyData(
        people=[
            dict(id=1, name="Primary", birth_date=date(1984, 1, 1), tax_kind="individual",
                 income_by_fy=dict(baseline), tax_complete=True),
            dict(id=2, name="Recipient", birth_date=date(1990, 1, 1), tax_kind="individual",
                 income_by_fy=dict(baseline), tax_complete=True),
        ],
        accounts=[
            dict(id=1, person_id=1, person="Primary", bank="Alpha", label="Alpha Primary",
                 cash=100_000, cash_known=True, existing_fd=300_000, terms_complete=True,
                 eligible=True, details=[], unknown_fds=0),
            dict(id=2, person_id=2, person="Recipient", bank="Beta", label="Beta · Recipient",
                 cash=50_000, cash_known=True, existing_fd=0, terms_complete=True,
                 eligible=True, details=[], unknown_fds=0),
        ],
    )
    bundles = {
        "Alpha": _verified_bundle("Alpha", 9.0, as_of),
        "Beta": _verified_bundle("Beta", 8.0, as_of),
    }
    initial_cash = sum(account["cash"] for account in data.accounts)
    reserve = 30_000
    bank_cap = (initial_cash + sum(a["existing_fd"] for a in data.accounts)) * 0.50
    assert data.accounts[0]["existing_fd"] > bank_cap

    plan = build_family_plan(
        data, bundles, reserve=reserve, months=12, family_pool=True,
        insurance=True, tax_limits=True, bank_percent=50, lot_size=1_000,
        time_limit=20, as_of=as_of,
    )

    # Independent household cash reconciliation and reserve check.
    assert plan.invested + plan.liquid == pytest.approx(initial_cash, abs=0.03)
    assert plan.liquid >= reserve - 0.03
    assert all(row["bank"] != "Alpha" for row in plan.allocations + plan.cash_allocations)

    # Exposure includes existing FDs, new maturity values, and retained cash
    # with its projected interest. Alpha was already above cap, so it gets no
    # new exposure; Beta remains within its household-wide headroom.
    beta_new_exposure = sum(row["maturity_amount"] for row in plan.allocations if row["bank"] == "Beta")
    beta_new_exposure += sum(row["amount"] + row["interest"] for row in plan.cash_allocations if row["bank"] == "Beta")
    assert beta_new_exposure <= bank_cap + 0.03

    # Transfer ledger must conserve each account's initial cash into its final
    # FD and retained-cash target, and conserve total flow across the family.
    initial_by_label = {account["label"]: account["cash"] for account in data.accounts}
    final_by_label = {account["label"]: 0.0 for account in data.accounts}
    for row in plan.allocations + plan.cash_allocations:
        final_by_label[row["account"]] += row["amount"]
    incoming = {label: 0.0 for label in initial_by_label}
    outgoing = {label: 0.0 for label in initial_by_label}
    for transfer in plan.transfers:
        outgoing[transfer["from_account"]] += transfer["amount"]
        incoming[transfer["to_account"]] += transfer["amount"]
    for label in initial_by_label:
        assert initial_by_label[label] + incoming[label] - outgoing[label] == pytest.approx(final_by_label[label], abs=0.03)
    assert sum(incoming.values()) == pytest.approx(sum(outgoing.values()), abs=0.03)

    # Annual projections remain below both the ₹50,000 interest limit and the
    # synthetic individual rebate headroom, without consulting solver helpers.
    assert plan.tax_complete
    assert plan.annual
    for row in plan.annual:
        assert row["baseline"] == 1_190_000
        assert row["complete"] is True
        assert 0 <= row["new_interest"] <= 10_000 + 0.03
        assert row["new_interest"] <= 50_000 + 0.03
        assert row["taxable_total"] <= 1_200_000 + 0.03

    # An optimal label requires a finite, closed solver gap. Existing timeout
    # coverage separately verifies a limited solve is labeled feasible.
    assert plan.status == "optimal"
    assert plan.gap is not None and math.isfinite(plan.gap) and 0 <= plan.gap <= 0.0001

