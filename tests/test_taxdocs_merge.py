"""
tests/test_taxdocs_merge.py — Tests for TIS/AIS/26AS document merging.

Covers presumptive profit calculation under s.44ADA with correct rounding.
"""

import pytest
from engines.taxdocs.merge import _apply_44ada_presumptive_profit, merge_tax_documents


class TestPresumptiveProfitRounding:
    """Test presumptive profit calculation with correct half-up rounding."""

    def test_presumptive_profit_105069_rounds_to_52535(self):
        """
        Gross receipts 1,05,069 should give presumptive profit exactly 52,535.
        105069 * 0.5 = 52534.5, which rounds UP to 52535 (not truncate to 52534).
        """
        result = _apply_44ada_presumptive_profit(105069)
        assert result['presumptive_profit'] == 52535, \
            f"Expected 52535 but got {result['presumptive_profit']}"
        assert result['is_applicable'] is True
        assert '50%' in result['rule']

    def test_presumptive_profit_halves_round_up(self):
        """
        Verify that .5 fractions round UP, not truncate or use banker's rounding.

        - 105069 * 0.5 = 52534.5 → rounds to 52535
        - 105070 * 0.5 = 52535.0 → stays 52535
        - 105071 * 0.5 = 52535.5 → rounds to 52536
        """
        # Test .5 rounding up (the key fix)
        result_105069 = _apply_44ada_presumptive_profit(105069)
        assert result_105069['presumptive_profit'] == 52535, \
            f"105069 * 0.5 = 52534.5 should round to 52535, got {result_105069['presumptive_profit']}"

        # Test exact integer (no rounding needed)
        result_105070 = _apply_44ada_presumptive_profit(105070)
        assert result_105070['presumptive_profit'] == 52535, \
            f"105070 * 0.5 = 52535.0 should be 52535, got {result_105070['presumptive_profit']}"

        # Test .5 rounding up (another case)
        result_105071 = _apply_44ada_presumptive_profit(105071)
        assert result_105071['presumptive_profit'] == 52536, \
            f"105071 * 0.5 = 52535.5 should round to 52536, got {result_105071['presumptive_profit']}"

    def test_presumptive_profit_zero_receipts(self):
        """Zero business receipts should give zero presumptive profit and not applicable."""
        result = _apply_44ada_presumptive_profit(0)
        assert result['presumptive_profit'] == 0.0
        assert result['is_applicable'] is False
        assert 'No business receipts' in result['rule']

    def test_presumptive_profit_large_amount(self):
        """Test with larger amounts to ensure rounding works at scale."""
        result = _apply_44ada_presumptive_profit(1000000)  # 1 million
        expected = 500000  # exactly half, no rounding needed
        assert result['presumptive_profit'] == expected, \
            f"Expected {expected} but got {result['presumptive_profit']}"


class TestMergeTaxDocuments:
    """Test the full merge_tax_documents function."""

    def test_merge_with_presumptive_profit_105069(self):
        """
        Test full merge with gross receipts 105,069.
        Expected: presumptive profit 52,535; total income 3,58,015.

        This assumes other income components:
        - dividend: 0
        - savings_interest: 0
        - fd_interest: 3,05,480
        Total: 52,535 + 3,05,480 = 3,58,015
        """
        tis_data = {
            'dividend': 0,
            'savings_interest': 0,
            'fd_interest': 305480,
            'business_receipts': 105069,
            'non_income': {'purchase_of_time_deposits': 0}
        }
        ais_data = {
            'dividend': 0,
            'savings_interest': 0,
            'fd_interest': 305480,
            'business_receipts': 105069,
            'tds': 0,
            'non_income': {},
            'details': []
        }
        form26as_data = {
            'total_tds': 0,
            'records': [],
            'part_ii': [],
            'refunds': {}
        }

        result = merge_tax_documents(tis_data, ais_data, form26as_data)

        # Verify presumptive profit is correctly rounded to 52,535
        assert result['financial_position']['presumptive_profit'] == 52535, \
            f"Expected presumptive_profit 52535 but got {result['financial_position']['presumptive_profit']}"

        # Verify total income is correctly calculated as 3,58,015
        assert result['financial_position']['total_income'] == 358015, \
            f"Expected total_income 358015 but got {result['financial_position']['total_income']}"

    def test_merge_basic_structure(self):
        """Test that merge returns required keys."""
        tis_data = {
            'dividend': 100000,
            'savings_interest': 50000,
            'fd_interest': 100000,
            'business_receipts': 200000,
            'non_income': {'purchase_of_time_deposits': 0}
        }
        ais_data = {
            'dividend': 100000,
            'savings_interest': 50000,
            'fd_interest': 100000,
            'business_receipts': 200000,
            'tds': 5000,
            'non_income': {},
            'details': []
        }
        form26as_data = {
            'total_tds': 5000,
            'records': [],
            'part_ii': [],
            'refunds': {}
        }

        result = merge_tax_documents(tis_data, ais_data, form26as_data)

        # Check required top-level keys
        assert 'financial_position' in result
        assert 'income_variance' in result
        assert 'tds_reconciliation' in result
        assert 'fd_matches' in result
        assert 'fd_not_in_app' in result
        assert 'non_income_items' in result

        # Check financial_position structure
        fp = result['financial_position']
        assert fp['dividend'] == 100000
        assert fp['savings_interest'] == 50000
        assert fp['fd_interest'] == 100000
        assert fp['business_receipts'] == 200000
        assert fp['presumptive_profit'] == 100000  # 200000 * 0.5
        assert fp['tds_deducted'] == 5000

    def test_merge_with_fd_matches(self):
        """Test FD account matching during merge."""
        def mock_fd_lookup(account_no):
            if account_no == 'ACC123':
                return {'fd_id': 'FD001'}
            return None

        tis_data = {
            'dividend': 0,
            'savings_interest': 0,
            'fd_interest': 50000,
            'business_receipts': 0,
            'non_income': {}
        }
        ais_data = {
            'dividend': 0,
            'savings_interest': 0,
            'fd_interest': 50000,
            'business_receipts': 0,
            'tds': 0,
            'non_income': {},
            'details': [
                {
                    'code': 'SFT-016(TD)',
                    'account_number': 'ACC123',
                    'amount': 50000,
                    'description': 'FD Interest'
                }
            ]
        }
        form26as_data = {
            'total_tds': 0,
            'records': [],
            'part_ii': [],
            'refunds': {}
        }

        result = merge_tax_documents(
            tis_data, ais_data, form26as_data,
            fd_by_account_no_lookup=mock_fd_lookup
        )

        # Check FD match was found
        assert 'ACC123' in result['fd_matches']
        assert result['fd_matches']['ACC123']['fd_id'] == 'FD001'
        assert result['fd_matches']['ACC123']['ais_amount'] == 50000

    def test_form26as_wins_on_tax_credit(self):
        """
        Authority rule: 26AS wins on tax credit.

        The merged tds_deducted must be 13367 from 26AS, NOT 12073 from AIS.
        This ensures the taxpayer gets credit only for what 26AS reports.
        """
        tis_data = {
            "dividend": 2655.0,
            "savings_interest": 46183.0,
            "fd_interest": 256642.0,
            "business_receipts": 105069.0,
            "non_income": {"purchase_of_time_deposits": 1300000.0}
        }
        ais_data = {
            "dividend": 2655.0,
            "savings_interest": 46183.0,
            "fd_interest": 256642.0,
            "business_receipts": 105069.0,
            "tds": 12073.0,
            "non_income": {"SFT-005": 1300000.0},
            "details": [
                {"code": "TDS-194A", "amount": 245389.0},
                {"code": "SFT-016(TD)", "amount": 256642.0, "account_number": "45220300154351221"}
            ]
        }
        form26as_data = {
            "pan": "AZIPT9702H",
            "name": "PRANAV ARVINDBHAI TANK",
            "assessment_year": "2026-27",
            "total_tds": 13367.0,
            "records": [],
            "part_ii": [],
            "refunds": {}
        }

        result = merge_tax_documents(tis_data, ais_data, form26as_data)

        # 26AS is authoritative on tax credit
        assert result['financial_position']['tds_deducted'] == 13367, \
            f"tds_deducted must be 13367 from 26AS, got {result['financial_position']['tds_deducted']}"
        # Explicitly verify it is NOT the AIS value
        assert result['financial_position']['tds_deducted'] != 12073, \
            f"tds_deducted must NOT be 12073 from AIS"

    def test_tds_disagreement_is_surfaced(self):
        """
        Authority rule: The disagreement is surfaced, not hidden.

        tds_reconciliation must report ais_tds (12073), form26as_tds (13367),
        and the difference (1294). The two documents genuinely disagree and the
        user must be able to see that discrepancy.
        """
        tis_data = {
            "dividend": 2655.0,
            "savings_interest": 46183.0,
            "fd_interest": 256642.0,
            "business_receipts": 105069.0,
            "non_income": {"purchase_of_time_deposits": 1300000.0}
        }
        ais_data = {
            "dividend": 2655.0,
            "savings_interest": 46183.0,
            "fd_interest": 256642.0,
            "business_receipts": 105069.0,
            "tds": 12073.0,
            "non_income": {"SFT-005": 1300000.0},
            "details": [
                {"code": "TDS-194A", "amount": 245389.0},
                {"code": "SFT-016(TD)", "amount": 256642.0, "account_number": "45220300154351221"}
            ]
        }
        form26as_data = {
            "pan": "AZIPT9702H",
            "name": "PRANAV ARVINDBHAI TANK",
            "assessment_year": "2026-27",
            "total_tds": 13367.0,
            "records": [],
            "part_ii": [],
            "refunds": {}
        }

        result = merge_tax_documents(tis_data, ais_data, form26as_data)

        recon = result['tds_reconciliation']
        assert recon['ais_tds'] == 12073, \
            f"ais_tds must be 12073, got {recon['ais_tds']}"
        assert recon['form26as_tds'] == 13367, \
            f"form26as_tds must be 13367, got {recon['form26as_tds']}"
        assert recon['difference'] == 1294, \
            f"difference must be 1294 (13367 - 12073), got {recon['difference']}"

    def test_ais_part_b1_and_b2_never_summed(self):
        """
        Authority rule: AIS Part B1 and Part B2 are never summed.

        TDS-194A (245389) and SFT-016(TD) (256642) are the same interest
        reported twice in different sections. The merged result must use
        256642 (from SFT-016), and 502031 (their sum) must not appear anywhere.
        """
        tis_data = {
            "dividend": 2655.0,
            "savings_interest": 46183.0,
            "fd_interest": 256642.0,
            "business_receipts": 105069.0,
            "non_income": {"purchase_of_time_deposits": 1300000.0}
        }
        ais_data = {
            "dividend": 2655.0,
            "savings_interest": 46183.0,
            "fd_interest": 256642.0,
            "business_receipts": 105069.0,
            "tds": 12073.0,
            "non_income": {"SFT-005": 1300000.0},
            "details": [
                {"code": "TDS-194A", "amount": 245389.0},
                {"code": "SFT-016(TD)", "amount": 256642.0, "account_number": "45220300154351221"}
            ]
        }
        form26as_data = {
            "pan": "AZIPT9702H",
            "name": "PRANAV ARVINDBHAI TANK",
            "assessment_year": "2026-27",
            "total_tds": 13367.0,
            "records": [],
            "part_ii": [],
            "refunds": {}
        }

        result = merge_tax_documents(tis_data, ais_data, form26as_data)

        # fd_interest must be 256642, not the sum
        assert result['financial_position']['fd_interest'] == 256642, \
            f"fd_interest must be 256642, got {result['financial_position']['fd_interest']}"

        # The sum 502031 must not appear anywhere in the result
        import json
        result_json = json.dumps(result)
        assert "502031" not in result_json, \
            "The sum 502031 (245389 + 256642) must not appear in the merged result"

    def test_non_income_never_enters_income(self):
        """
        Authority rule: Non-income never enters income.

        The 1300000 purchase of time deposits must be flagged in the
        non_income_items section AND must NOT appear in any income total.
        The total_income must be 358015, not inflated by non-income.
        """
        tis_data = {
            "dividend": 2655.0,
            "savings_interest": 46183.0,
            "fd_interest": 256642.0,
            "business_receipts": 105069.0,
            "non_income": {"purchase_of_time_deposits": 1300000.0}
        }
        ais_data = {
            "dividend": 2655.0,
            "savings_interest": 46183.0,
            "fd_interest": 256642.0,
            "business_receipts": 105069.0,
            "tds": 12073.0,
            "non_income": {"SFT-005": 1300000.0},
            "details": [
                {"code": "TDS-194A", "amount": 245389.0},
                {"code": "SFT-016(TD)", "amount": 256642.0, "account_number": "45220300154351221"}
            ]
        }
        form26as_data = {
            "pan": "AZIPT9702H",
            "name": "PRANAV ARVINDBHAI TANK",
            "assessment_year": "2026-27",
            "total_tds": 13367.0,
            "records": [],
            "part_ii": [],
            "refunds": {}
        }

        result = merge_tax_documents(tis_data, ais_data, form26as_data)

        # total_income must be 358015
        # (2655 + 46183 + 256642 + 52535, where 52535 = 105069 * 0.5 rounded up)
        assert result['financial_position']['total_income'] == 358015, \
            f"total_income must be 358015, got {result['financial_position']['total_income']}"

        # 1300000 must be in non_income_items
        assert result['non_income_items']['purchase_of_time_deposits'] == 1300000.0

        # 1300000 must NOT appear in the income section
        import json
        income_json = json.dumps(result['financial_position'])
        assert "1300000" not in income_json, \
            "The non-income amount 1300000 must not appear in the financial_position (income) section"

    def test_fd_account_matching_works(self):
        """
        Authority rule: FD account matching works.

        When a lookup function is provided that resolves 45220300154351221
        to an FD record, that AIS deposit account must be reported as matched
        in the fd_matches section.
        """
        def mock_fd_lookup(account_no):
            # Only this account matches
            if account_no == "45220300154351221":
                return {"fd_id": "FD-7890"}
            return None

        tis_data = {
            "dividend": 2655.0,
            "savings_interest": 46183.0,
            "fd_interest": 256642.0,
            "business_receipts": 105069.0,
            "non_income": {"purchase_of_time_deposits": 1300000.0}
        }
        ais_data = {
            "dividend": 2655.0,
            "savings_interest": 46183.0,
            "fd_interest": 256642.0,
            "business_receipts": 105069.0,
            "tds": 12073.0,
            "non_income": {"SFT-005": 1300000.0},
            "details": [
                {"code": "TDS-194A", "amount": 245389.0},
                {"code": "SFT-016(TD)", "amount": 256642.0, "account_number": "45220300154351221"}
            ]
        }
        form26as_data = {
            "pan": "AZIPT9702H",
            "name": "PRANAV ARVINDBHAI TANK",
            "assessment_year": "2026-27",
            "total_tds": 13367.0,
            "records": [],
            "part_ii": [],
            "refunds": {}
        }

        result = merge_tax_documents(
            tis_data, ais_data, form26as_data,
            fd_by_account_no_lookup=mock_fd_lookup
        )

        # The account must be in fd_matches with the matched FD
        assert "45220300154351221" in result['fd_matches'], \
            "Account 45220300154351221 must be in fd_matches"
        assert result['fd_matches']["45220300154351221"]['fd_id'] == "FD-7890"
        assert result['fd_matches']["45220300154351221"]['ais_amount'] == 256642.0

    def test_unmatched_ais_accounts_are_reported(self):
        """
        Authority rule: Unmatched AIS accounts are reported, not dropped.

        When a lookup function finds no match for an AIS account,
        that account must appear in the fd_not_in_app list. Silently
        dropping an account the tax department knows about is a data loss
        that must be prevented.
        """
        def mock_fd_lookup(account_no):
            # Lookup always returns None (no matches)
            return None

        tis_data = {
            "dividend": 2655.0,
            "savings_interest": 46183.0,
            "fd_interest": 256642.0,
            "business_receipts": 105069.0,
            "non_income": {"purchase_of_time_deposits": 1300000.0}
        }
        ais_data = {
            "dividend": 2655.0,
            "savings_interest": 46183.0,
            "fd_interest": 256642.0,
            "business_receipts": 105069.0,
            "tds": 12073.0,
            "non_income": {"SFT-005": 1300000.0},
            "details": [
                {"code": "TDS-194A", "amount": 245389.0},
                {"code": "SFT-016(TD)", "amount": 256642.0, "account_number": "45220300154351221"}
            ]
        }
        form26as_data = {
            "pan": "AZIPT9702H",
            "name": "PRANAV ARVINDBHAI TANK",
            "assessment_year": "2026-27",
            "total_tds": 13367.0,
            "records": [],
            "part_ii": [],
            "refunds": {}
        }

        result = merge_tax_documents(
            tis_data, ais_data, form26as_data,
            fd_by_account_no_lookup=mock_fd_lookup
        )

        # The account must be in fd_not_in_app because lookup returned None
        assert "45220300154351221" in result['fd_not_in_app'], \
            "Unmatched account 45220300154351221 must be in fd_not_in_app"
