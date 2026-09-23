"""
Cleans the raw Olist order reviews table and reduces it to one score per order.
"""

import pandas as pd

RAW_PATH = "../data/raw/olist_order_reviews_dataset.csv"
PROCESSED_PATH = "../data/processed/reviews.parquet"

TIMESTAMP_COLUMNS = ["review_answer_timestamp"]


def load_reviews(path: str = RAW_PATH) -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=TIMESTAMP_COLUMNS)


# A second review is the customer's later verdict on the same order, so the
# latest answer wins. Averaging would invent a score nobody actually gave.
def deduplicate_reviews(reviews: pd.DataFrame) -> pd.DataFrame:
    """Keep one review per order - the last one the customer submitted."""
    by_answer_date = reviews.sort_values("review_answer_timestamp")
    return by_answer_date.drop_duplicates("order_id", keep="last")


def clean_reviews(reviews: pd.DataFrame) -> pd.DataFrame:
    """Reduce the raw reviews table to one score per order."""
    deduplicated = deduplicate_reviews(reviews)

    # Comment text answers none of the project's questions, and the timestamp
    # is only borrowed above to put the reviews in order.
    return deduplicated[["order_id", "review_score"]]


def main():
    reviews = load_reviews()
    df = clean_reviews(reviews)
    df.to_parquet(PROCESSED_PATH, index=False)

    print("rows:", len(df))
    print("unique orders:", df["order_id"].nunique())
    print(df["review_score"].value_counts().sort_index())


if __name__ == "__main__":
    main()