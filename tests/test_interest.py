from engines.interest_engine import calculate_fd_maturity, calculate_fd_maturity_bank_style, _update_fd_interest_rollup
from datetime import date
from models.fixed_deposit import add_fd, add_fd_from_statement, get_fd
from models.fd_interest_record import get_fd_interest_by_fy, get_total_fd_interest, get_total_fd_interest_for_fd
from models.person import add_person
from models.bank_account import add_account


def test_fd_maturity_formula_monthly():
    m = calculate_fd_maturity(10000, 6.0, 12, "Monthly")
    assert isinstance(m, float)
    assert m > 10000


def test_fd_maturity_bank_style_simple():
    start = date(2024, 1, 1)
    end = date(2025, 1, 1)
    m = calculate_fd_maturity_bank_style(50000, 7.0, start, end, "Quarterly")
    assert isinstance(m, float)
    assert m >= 50000


class TestFDAllocationFromModel:
    """Test FD interest allocation from model-level functions."""

    def test_add_fd_allocates_interest(self):
        """Creating an FD via add_fd() should allocate interest to FY."""
        # Setup: Create person and account
        person_id = add_person("Test Person", date_of_birth="1990-01-01")
        account_id = add_account(
            person_id=person_id,
            bank_name="Test Bank",
            account_type="Savings",
            account_number_full="1234567890",
            ifsc_code="TEST0001"
        )

        # Create FD with complete maturity details
        start_date = "2026-02-24"
        maturity_date = "2026-09-13"
        principal = 100000.0
        rate = 8.0

        # Calculate expected maturity using formula
        start_py = date.fromisoformat(start_date)
        maturity_py = date.fromisoformat(maturity_date)
        maturity_amount = calculate_fd_maturity_bank_style(
            principal, rate, start_py, maturity_py, "Quarterly"
        )

        fd_id = add_fd(
            account_id=account_id,
            person_id=person_id,
            principal_amount=principal,
            start_date=start_date,
            tenure_months=6,  # approximate
            interest_rate=rate,
            compounding_type="Quarterly",
            maturity_date=maturity_date,
            maturity_amount=maturity_amount,
            maturity_amount_formula=maturity_amount,
            maturity_amount_bank=maturity_amount,
            maturity_calc_method="BankStyle",
            tenure_years=0,
            tenure_days=0,
        )

        # Verify FD was created
        fd = get_fd(fd_id)
        assert fd is not None
        assert fd["fd_id"] == fd_id
        assert fd["principal_amount"] == principal

        # Verify interest was allocated to FY2026-27 (first credit event is after April 1, 2026)
        # Even though start date is in FY2025-26, the interest is credited in FY2026-27
        fy_records = get_fd_interest_by_fy("2026-27", person_id=person_id)
        fd_records = [r for r in fy_records if r["fd_id"] == fd_id]

        assert len(fd_records) > 0, f"No FDInterestRecord created for allocated FD. All records: {fy_records}"

        # Verify total interest is non-zero and reasonable
        total_interest = get_total_fd_interest("2026-27", person_id=person_id)
        assert total_interest > 0, f"No interest allocated to FY2026-27. Total={total_interest}"

        # Verify the interest amount is reasonable (should be around 4496 for bank-style)
        total_for_fd = sum(r["interest_earned"] for r in fd_records)
        assert 4400 < total_for_fd < 4600, f"Interest {total_for_fd} not in expected range [4400, 4600]"

    def test_add_fd_from_statement_with_null_maturity_no_crash(self):
        """Creating an FD via add_fd_from_statement() with NULL maturity should not crash."""
        # Setup: Create person and account
        person_id = add_person("Statement Test", date_of_birth="1985-01-15")
        account_id = add_account(
            person_id=person_id,
            bank_name="Test Bank Statement",
            account_type="Savings",
            account_number_full="9876543210",
            ifsc_code="TEST0002"
        )

        # Create "Pending Details" FD with NULL maturity (statement import case)
        fd_id = add_fd_from_statement(
            account_id=account_id,
            person_id=person_id,
            principal_amount=50000.0,
            start_date="2026-01-15",
            fd_reference_no="FD123456",
            tenure_months=None,  # NULL
            interest_rate=None,  # NULL
            compounding_type=None,  # NULL
            maturity_date=None,  # NULL maturity
            maturity_amount=None,
            expected_interest_amount=None,
            source_statement_file="test.pdf",
            source_transaction_id=None,  # No transaction ID for this pending FD
        )

        # Verify FD was created despite NULL maturity
        assert fd_id > 0, "FD should have been created"

        fd = get_fd(fd_id)
        assert fd is not None
        assert fd["status"] == "Pending Details"
        assert fd["maturity_date"] is None, "Maturity date should be NULL"

        # Verify no interest records were created (safe no-op for NULL maturity)
        fy_records = get_fd_interest_by_fy("2025-26", person_id=person_id)
        fd_records = [r for r in fy_records if r["fd_id"] == fd_id]
        assert len(fd_records) == 0, "No FDInterestRecord should be created for Pending Details FD"

    def test_fd_interest_rollup_updates_summary_columns(self):
        """Verify that FD interest rollup populates expected_interest_amount and actual_interest_amount."""
        # Setup: Create person and account
        person_id = add_person("Rollup Test", date_of_birth="1988-06-15")
        account_id = add_account(
            person_id=person_id,
            bank_name="Test Bank Rollup",
            account_type="Savings",
            account_number_full="5555555555",
            ifsc_code="TEST0003"
        )

        # Create FD with complete maturity details (1-year tenure)
        start_date = "2026-02-24"
        maturity_date = "2027-02-24"
        principal = 100000.0
        rate = 8.0

        # Calculate expected maturity
        start_py = date.fromisoformat(start_date)
        maturity_py = date.fromisoformat(maturity_date)
        maturity_amount = calculate_fd_maturity_bank_style(
            principal, rate, start_py, maturity_py, "Quarterly"
        )

        fd_id = add_fd(
            account_id=account_id,
            person_id=person_id,
            principal_amount=principal,
            start_date=start_date,
            tenure_months=12,
            interest_rate=rate,
            compounding_type="Quarterly",
            maturity_date=maturity_date,
            maturity_amount=maturity_amount,
            maturity_amount_formula=maturity_amount,
            maturity_amount_bank=maturity_amount,
            maturity_calc_method="BankStyle",
            tenure_years=1,
            tenure_days=0,
        )

        # Verify FD was created
        fd = get_fd(fd_id)
        assert fd is not None
        assert fd["fd_id"] == fd_id

        # After add_fd(), the rollup should have been called via allocate_fd_interest_to_fy()
        # So expected_interest_amount and actual_interest_amount should be populated
        expected_interest = fd["expected_interest_amount"]
        actual_interest = fd["actual_interest_amount"]

        # Verify rollup columns are non-None and match the calculated interest
        assert expected_interest is not None, "expected_interest_amount should be populated by rollup"
        assert actual_interest is not None, "actual_interest_amount should be populated by rollup"

        # Calculate what the total should be from FDInterestRecord
        total_from_records = get_total_fd_interest_for_fd(fd_id)
        assert total_from_records > 0, "FDInterestRecord should have calculated interest"

        # Verify both columns match the sum from FDInterestRecord
        assert expected_interest == total_from_records, \
            f"expected_interest_amount {expected_interest} should equal FDInterestRecord sum {total_from_records}"
        assert actual_interest == total_from_records, \
            f"actual_interest_amount {actual_interest} should equal FDInterestRecord sum {total_from_records}"
