"""
Tests for the shipping-deadline logic in cleaning/clean_order_items.py.
"""

import pandas as pd

from cleaning.clean_order_items import flag_missed_shipping_deadline


def dates(*values) -> pd.Series:
    """Build a datetime Series from plain strings, so each test stays readable."""
    return pd.to_datetime(pd.Series(list(values)))


def test_missed_deadline_is_true_when_handed_over_after_the_limit():
    # Arrange
    limit = dates("2018-01-03 12:00")
    carrier = dates("2018-01-05 09:00")

    # Act
    result = flag_missed_shipping_deadline(limit, carrier)

    # Assert
    assert result.iloc[0]


def test_missed_deadline_is_false_when_handed_over_before_the_limit():
    limit = dates("2018-01-05 12:00")
    carrier = dates("2018-01-03 09:00")

    result = flag_missed_shipping_deadline(limit, carrier)

    assert not result.iloc[0]


def test_missed_deadline_is_na_when_the_carrier_date_is_missing():
    limit = dates("2018-01-03 12:00")
    carrier = dates(None)

    result = flag_missed_shipping_deadline(limit, carrier)

    assert pd.isna(result.iloc[0])