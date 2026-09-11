"""
Tests for the delay and stage-duration logic in cleaning/clean_orders.py.
"""

import pandas as pd

from cleaning.clean_orders import (
    compute_delay_days,
    compute_is_late,
    compute_stage_hours,
    flag_out_of_order,
)


def dates(*values) -> pd.Series:
    """Build a datetime Series from plain strings, so each test stays readable."""
    return pd.to_datetime(pd.Series(list(values)))


# --- compute_delay_days ---

def test_delay_days_is_zero_when_delivered_on_the_promised_day():
    # Arrange
    delivered = dates("2018-01-03 14:32")
    estimated = dates("2018-01-03")

    # Act
    result = compute_delay_days(delivered, estimated)

    # Assert
    assert result.iloc[0] == 0


def test_delay_days_is_positive_when_delivered_after_the_promised_date():
    delivered = dates("2018-01-05 09:00")
    estimated = dates("2018-01-03")

    result = compute_delay_days(delivered, estimated)

    assert result.iloc[0] == 2


def test_delay_days_is_negative_when_delivered_early():
    delivered = dates("2018-01-01 09:00")
    estimated = dates("2018-01-03")

    result = compute_delay_days(delivered, estimated)

    assert result.iloc[0] == -2


def test_delay_days_is_na_when_the_delivery_date_is_missing():
    delivered = dates(None)
    estimated = dates("2018-01-03")

    result = compute_delay_days(delivered, estimated)

    assert pd.isna(result.iloc[0])


# --- compute_is_late ---

def test_is_late_is_true_when_the_delay_is_positive():
    delay = pd.Series([2], dtype="Int64")

    result = compute_is_late(delay)

    assert result.iloc[0]


def test_is_late_is_false_when_delivered_on_the_promised_day():
    delay = pd.Series([0], dtype="Int64")

    result = compute_is_late(delay)

    assert not result.iloc[0]


def test_is_late_is_na_when_the_delay_is_unknown():
    delay = pd.Series([pd.NA], dtype="Int64")

    result = compute_is_late(delay)

    assert pd.isna(result.iloc[0])


# --- compute_stage_hours ---

def test_stage_hours_measures_the_gap_in_hours():
    start = dates("2018-01-03 10:00")
    end = dates("2018-01-03 12:00")

    result = compute_stage_hours(start, end)

    assert result.iloc[0] == 2.0


def test_stage_hours_is_na_when_the_gap_is_negative():
    start = dates("2018-01-06 08:00")
    end = dates("2018-01-05 08:00")

    result = compute_stage_hours(start, end)

    assert pd.isna(result.iloc[0])


# --- flag_out_of_order ---

def test_flag_out_of_order_is_true_when_the_later_date_comes_first():
    earlier = dates("2018-01-06 08:00")
    later = dates("2018-01-05 08:00")

    result = flag_out_of_order(earlier, later)

    assert result.iloc[0]


def test_flag_out_of_order_is_false_when_the_dates_are_in_order():
    earlier = dates("2018-01-03 12:00")
    later = dates("2018-01-06 08:00")

    result = flag_out_of_order(earlier, later)

    assert not result.iloc[0]


def test_flag_out_of_order_is_na_when_a_date_is_missing():
    earlier = dates(None)
    later = dates("2018-01-07 09:00")

    result = flag_out_of_order(earlier, later)

    assert pd.isna(result.iloc[0])