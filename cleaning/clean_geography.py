"""
Cleans the Olist geography tables and derives seller-to-customer distances.
"""

import numpy as np
import pandas as pd

RAW_GEOLOCATION_PATH = "../data/raw/olist_geolocation_dataset.csv"
RAW_CUSTOMERS_PATH = "../data/raw/olist_customers_dataset.csv"
RAW_SELLERS_PATH = "../data/raw/olist_sellers_dataset.csv"
ORDERS_PATH = "../data/processed/orders.parquet"
ORDER_ITEMS_PATH = "../data/processed/order_items.parquet"

PROCESSED_GEOLOCATION_PATH = "../data/processed/geolocation.parquet"
PROCESSED_CUSTOMERS_PATH = "../data/processed/customers.parquet"
PROCESSED_SELLERS_PATH = "../data/processed/sellers.parquet"
PROCESSED_DISTANCES_PATH = "../data/processed/order_distances.parquet"

EARTH_RADIUS_KM = 6371


def load_geolocation(path: str = RAW_GEOLOCATION_PATH) -> pd.DataFrame:
    return pd.read_csv(path)


def load_customers(path: str = RAW_CUSTOMERS_PATH) -> pd.DataFrame:
    return pd.read_csv(path)


def load_sellers(path: str = RAW_SELLERS_PATH) -> pd.DataFrame:
    return pd.read_csv(path)


def load_orders(path: str = ORDERS_PATH) -> pd.DataFrame:
    return pd.read_parquet(path, columns=["order_id", "customer_id"])


def load_order_items(path: str = ORDER_ITEMS_PATH) -> pd.DataFrame:
    return pd.read_parquet(path, columns=["order_id", "order_item_id", "seller_id"])


# Some coordinates fall far outside Brazil (31 rows across 20 prefixes) - clear
# geocoding errors. The median then guards against whatever the filter misses.
def aggregate_geolocation(geo: pd.DataFrame) -> pd.DataFrame:
    """Reduce geolocation to one coordinate pair per zip code prefix."""
    in_brazil = (
        geo["geolocation_lat"].between(-34, 6)
        & geo["geolocation_lng"].between(-75, -28)
    )

    return (
        geo[in_brazil]
        .groupby("geolocation_zip_code_prefix")[["geolocation_lat", "geolocation_lng"]]
        .median()
        .reset_index()
    )


# The prefix keeps customer and seller coordinates apart; without it the second
# merge would silently rename both to geolocation_lat_x and geolocation_lat_y.
def add_coordinates(df: pd.DataFrame, zip_column: str, geo: pd.DataFrame, prefix: str) -> pd.DataFrame:
    """Attach the coordinate pair matching each row's zip code prefix."""
    coords = geo.rename(columns={
        "geolocation_zip_code_prefix": zip_column,
        "geolocation_lat": f"{prefix}_lat",
        "geolocation_lng": f"{prefix}_lng",
    })

    return df.merge(coords, on=zip_column, how="left", validate="many_to_one")


# Great-circle distance on a sphere: a straight line over the surface, not a road
# distance, and the Earth is not a perfect sphere. Good enough to compare orders
# against each other, which is all the distance question needs.
def haversine(lat1: pd.Series, lng1: pd.Series, lat2: pd.Series, lng2: pd.Series) -> pd.Series:
    """Distance in kilometres between two sets of coordinates."""
    lat1, lng1, lat2, lng2 = map(np.radians, (lat1, lng1, lat2, lng2))

    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlng / 2) ** 2

    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


def build_distances(
    items: pd.DataFrame,
    orders: pd.DataFrame,
    customers: pd.DataFrame,
    sellers: pd.DataFrame,
) -> pd.DataFrame:
    """One straight-line seller-to-customer distance per order item."""
    df = items.merge(orders, on="order_id", how="left", validate="many_to_one")

    df = df.merge(
        customers[["customer_id", "customer_lat", "customer_lng"]],
        on="customer_id",
        how="left",
        validate="many_to_one",
    )

    df = df.merge(
        sellers[["seller_id", "seller_lat", "seller_lng"]],
        on="seller_id",
        how="left",
        validate="many_to_one",
    )

    df["distance_km"] = haversine(
        df["seller_lat"], df["seller_lng"], df["customer_lat"], df["customer_lng"]
    )

    # The coordinates were only borrowed to compute the distance; they belong to
    # the customers and sellers tables, not here.
    return df[["order_id", "order_item_id", "distance_km"]]


def main():
    geo = aggregate_geolocation(load_geolocation())
    customers = load_customers()
    sellers = load_sellers()

    customers_geo = add_coordinates(customers, "customer_zip_code_prefix", geo, "customer")
    sellers_geo = add_coordinates(sellers, "seller_zip_code_prefix", geo, "seller")
    distances = build_distances(load_order_items(), load_orders(), customers_geo, sellers_geo)

    geo.to_parquet(PROCESSED_GEOLOCATION_PATH, index=False)
    customers.to_parquet(PROCESSED_CUSTOMERS_PATH, index=False)
    sellers.to_parquet(PROCESSED_SELLERS_PATH, index=False)
    distances.to_parquet(PROCESSED_DISTANCES_PATH, index=False)

    print("geolocation prefixes:", len(geo))
    print("order items:", len(distances))
    print("missing distance:", distances["distance_km"].isna().sum())
    print(distances["distance_km"].describe())


if __name__ == "__main__":
    main()