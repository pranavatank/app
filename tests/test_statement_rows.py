"""Visual row grouping must not depend on an arbitrary rounding grid."""
import pytest

from engines.statement.rows import cluster_into_rows


def word(text, x, top):
    return dict(text=text, x0=x, x1=x + 10, top=top, bottom=top + 8)


def test_nearby_transaction_fields_across_rounding_boundary_share_row():
    debit = word("100000.00", 365, 592.44)
    balance = word("400000.00", 530, 592.63)
    date = word("04-Oct-2025", 30, 592.63)
    assert cluster_into_rows([balance, date, debit]) == [[date, debit, balance]]


def test_rows_sort_vertically_and_words_sort_by_column():
    header = [word("Date", 30, 100), word("Balance", 530, 100.2)]
    transaction = [word("04-Oct-2025", 30, 120), word("100.00", 365, 120.1)]
    continuation = word("continued", 200, 130)
    assert cluster_into_rows([continuation, *reversed(transaction), *reversed(header)]) == [
        header, transaction, [continuation],
    ]


def test_close_words_do_not_bridge_separate_lines():
    a, b, c = [word(str(i), i * 20, top) for i, top in enumerate([100, 102, 104])]
    assert cluster_into_rows([c, b, a]) == [[a, b], [c]]


def test_page_calls_have_independent_row_anchors():
    first_page = word("footer", 10, 700)
    second_page = word("header", 10, 30)
    assert cluster_into_rows([first_page]) == [[first_page]]
    assert cluster_into_rows([second_page]) == [[second_page]]
    assert cluster_into_rows([]) == []


def test_tolerance_is_inclusive_and_configurable():
    a, b = word("a", 10, 100), word("b", 20, 103)
    assert cluster_into_rows([a, b]) == [[a, b]]
    assert cluster_into_rows([a, b], tolerance=2) == [[a], [b]]
    with pytest.raises(ValueError, match="nonnegative"):
        cluster_into_rows([a], tolerance=-1)
