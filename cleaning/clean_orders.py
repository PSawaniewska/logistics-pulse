"""
Cleans the raw Olist orders table and derives delivery delay features.
"""

import pandas as pd

RAW_PATH = "../data/raw/olist_orders_dataset.csv"
PROCESSED_PATH = "../data/processed/orders.parquet"

TIMESTAMP_COLUMNS = [
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date"
]


def load_orders(path: str = RAW_PATH) -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=TIMESTAMP_COLUMNS)


# The promised date carries no meaningful time-of-day, the actual delivery does.
# Comparing raw timestamps would mark same-day deliveries as late.
def compute_delay_days(delivered: pd.Series, estimated: pd.Series) -> pd.Series:
    """Whole days between the promised and the actual delivery date."""
    delay = delivered.dt.normalize() - estimated.dt.normalize()
    return delay.dt.days.astype("Int64")


# An order with no delivery date is unknown, not on time. Coercing it to False
# would count it as delivered on schedule and inflate the on-time rate.
def compute_is_late(delay_days: pd.Series) -> pd.Series:
    """Flag orders delivered after the promised date; NA where the delay is unknown."""
    return delay_days > 0


# A negative duration means the two timestamps contradict each other. Zeroing it
# would claim the stage took no time; NA says the value is unknown instead.
def compute_stage_hours(start: pd.Series, end: pd.Series) -> pd.Series:
    """Duration of one supply-chain stage, in hours."""
    hours = (end - start).dt.total_seconds() / 3600
    return hours.mask(hours < 0)


# A comparison against a missing date silently returns False, which reads as
# "no anomaly" rather than "unknown" - mask those rows instead.
def flag_out_of_order(earlier: pd.Series, later: pd.Series) -> pd.Series:
    """Flag rows where the two timestamps are in the wrong order."""
    anomaly = (later < earlier).astype("boolean")
    return anomaly.mask(earlier.isna() | later.isna())


def clean_orders(orders: pd.DataFrame) -> pd.DataFrame:
    """Add delay, stage-duration and data-quality columns to the raw orders table."""
    df = orders.copy()  # keep the caller's raw frame untouched

    df["delay_days"] = compute_delay_days(
        df["order_delivered_customer_date"],
        df["order_estimated_delivery_date"]
    )

    df["is_late"] = compute_is_late(df["delay_days"])

    df["approval_hours"] = compute_stage_hours(
        df["order_purchase_timestamp"],
        df["order_approved_at"]
    )

    df["preparation_hours"] = compute_stage_hours(
        df["order_approved_at"],
        df["order_delivered_carrier_date"]
    )

    df["transit_hours"] = compute_stage_hours(
        df["order_delivered_carrier_date"],
        df["order_delivered_customer_date"]
    )

    # Two named flags rather than one generic "anomaly" column: each points at a
    # different stage, and Limitations has to quote them separately.
    df["carrier_before_approved"] = flag_out_of_order(
        df["order_approved_at"],
        df["order_delivered_carrier_date"]
    )

    df["delivered_before_carrier"] = flag_out_of_order(
        df["order_delivered_carrier_date"],
        df["order_delivered_customer_date"]
    )

    return df


def main():
    orders = load_orders()
    df = clean_orders(orders)
    df.to_parquet(PROCESSED_PATH, index=False)

    print("rows:", len(df))
    print("carrier_before_approved:", df["carrier_before_approved"].sum())
    print("delivered_before_carrier:", df["delivered_before_carrier"].sum())


if __name__ == "__main__":
    main()