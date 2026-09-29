"""
Test that all taxable and non-taxable income categories are included in config.INCOME_CATEGORIES.
"""

from config import INCOME_CATEGORIES
from engines.prediction_engine import TAXABLE_INCOME_CATEGORIES, NON_TAXABLE_INCOME_CATEGORIES


def test_income_categories_superset():
    """All taxable and non-taxable categories must be available in INCOME_CATEGORIES."""
    all_category_sets = TAXABLE_INCOME_CATEGORIES | NON_TAXABLE_INCOME_CATEGORIES
    income_categories_set = set(INCOME_CATEGORIES)

    assert all_category_sets <= income_categories_set, (
        f"Missing categories: {all_category_sets - income_categories_set}"
    )
