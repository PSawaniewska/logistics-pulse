"""
Cleans the raw Olist order items table and flags missed shipping deadlines.
"""

import pandas as pd

RAW_PATH = "../data/raw/olist_order_items_dataset.csv"
PROCESSED_PATH = "../data/processed/order_items.parquet"
ORDERS_PATH = "../data/processed/orders.parquet"

TIMESTAMP_COLUMNS = ["shipping_limit_date"]


def load_order_items(path: str = RAW_PATH) -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=TIMESTAMP_COLUMNS)


# The carrier handoff date lives in orders, not here. Reading it from the cleaned
# Parquet keeps a single source of truth and makes clean_orders.py a prerequisite.
def load_carrier_dates(path: str = ORDERS_PATH) -> pd.DataFrame:
    return pd.read_parquet(path, columns=["order_id", "order_delivered_carrier_date"])


# A missing carrier date means we do not know whether the deadline was met.
# The comparison alone would answer False, which reads as "on time".
def flag_missed_shipping_deadline(limit: pd.Series, carrier: pd.Series) -> pd.Series:
    """Flag items handed to the carrier after the seller's shipping deadline."""
    missed = (carrier > limit).astype("boolean")
    return missed.mask(limit.isna() | carrier.isna())


def clean_order_items(items: pd.DataFrame, carrier_dates: pd.DataFrame) -> pd.DataFrame:
    """Add the missed-shipping-deadline flag to the raw order items table."""
    df = items.merge(carrier_dates, on="order_id", how="left", validate="many_to_one")

    df["missed_shipping_deadline"] = flag_missed_shipping_deadline(
        df["shipping_limit_date"],
        df["order_delivered_carrier_date"],
    )

    # The carrier date belongs to orders and is only borrowed for the flag above;
    # keeping it here would duplicate the same value in two tables.
    return df.drop(columns=["order_delivered_carrier_date"])


def main():
    items = load_order_items()
    carrier_dates = load_carrier_dates()
    df = clean_order_items(items, carrier_dates)
    df.to_parquet(PROCESSED_PATH, index=False)

    print("rows:", len(df))
    print("missed_shipping_deadline:", df["missed_shipping_deadline"].sum())
    print("unknown (no carrier date):", df["missed_shipping_deadline"].isna().sum())


if __name__ == "__main__":
    main()




