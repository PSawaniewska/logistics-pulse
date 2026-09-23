"""
Tests for the deduplication logic in cleaning/clean_reviews.py.
"""

import pandas as pd

from cleaning.clean_reviews import clean_reviews, deduplicate_reviews


def reviews(rows: list[tuple[str, int, str]]) -> pd.DataFrame:
    """Build a reviews frame from (order_id, score, answer date) tuples."""
    return pd.DataFrame({
        "order_id": [row[0] for row in rows],
        "review_score": [row[1] for row in rows],
        "review_comment_message": ["" for _ in rows],
        "review_answer_timestamp": pd.to_datetime([row[2] for row in rows]),
    })


def test_deduplicate_reviews_keeps_the_score_from_the_latest_answer():
    # Arrange
    df = reviews([
        ("A", 5, "2018-03-01 10:00"),
        ("A", 2, "2018-03-15 09:00"),
    ])

    # Act
    result = deduplicate_reviews(df)

    # Assert
    assert len(result) == 1
    assert result["review_score"].iloc[0] == 2


def test_deduplicate_reviews_keeps_the_latest_answer_even_when_rows_are_unordered():
    df = reviews([
        ("A", 2, "2018-03-15 09:00"),
        ("A", 5, "2018-03-01 10:00"),
    ])

    result = deduplicate_reviews(df)

    assert result["review_score"].iloc[0] == 2


def test_deduplicate_reviews_leaves_orders_with_a_single_review_untouched():
    df = reviews([
        ("A", 4, "2018-03-01 10:00"),
        ("B", 1, "2018-03-02 10:00"),
    ])

    result = deduplicate_reviews(df)

    assert len(result) == 2
    assert set(result["order_id"]) == {"A", "B"}


def test_clean_reviews_returns_only_the_order_id_and_the_score():
    df = reviews([("A", 4, "2018-03-01 10:00")])

    result = clean_reviews(df)

    assert list(result.columns) == ["order_id", "review_score"]