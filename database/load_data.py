"""
Builds the DuckDB database from the cleaned parquet files.
"""

import duckdb

PROCESSED_DIR = "../data/processed"
SCHEMA_PATH = "../sql/schema.sql"
DB_PATH = "../data/warehouse/logistics_pulse.duckdb"

# Foreign keys are checked on insert, so a table can only be loaded after the
# tables it points to. Each name is also the name of its parquet file.
LOAD_ORDER = ["customers", "sellers", "products", "geolocation", "orders", "reviews"]


def create_schema(con: duckdb.DuckDBPyConnection) -> None:
    """Create every table defined in sql/schema.sql."""
    with open(SCHEMA_PATH, encoding="utf-8") as file:
        con.execute(file.read())


# BY NAME matches parquet columns to table columns by name instead of position,
# so two columns of the same type cannot silently swap places.
def load_table(con: duckdb.DuckDBPyConnection, table: str) -> None:
    """Load one table from the parquet file of the same name."""
    con.execute(
        f"INSERT INTO {table} BY NAME SELECT * FROM '{PROCESSED_DIR}/{table}.parquet'"
    )


# The distance sits in its own file so that neither cleaning script overwrites
# the other's output. The two are joined here, on the way into the database.
def load_order_items(con: duckdb.DuckDBPyConnection) -> None:
    """Load order items, attaching the straight-line distance of each item."""
    con.execute(f"""
        INSERT INTO order_items BY NAME
        SELECT i.*, d.distance_km
        FROM '{PROCESSED_DIR}/order_items.parquet' i
        LEFT JOIN '{PROCESSED_DIR}/order_distances.parquet' d
            USING (order_id, order_item_id)
    """)


def count_rows(con: duckdb.DuckDBPyConnection, table: str) -> int:
    """Count the rows a table ended up with."""
    return con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def main():
    con = duckdb.connect(DB_PATH)

    create_schema(con)
    for table in LOAD_ORDER:
        load_table(con, table)
    load_order_items(con)

    for table in LOAD_ORDER + ["order_items"]:
        print(f"{table}: {count_rows(con, table)}")

    con.close()


if __name__ == "__main__":
    main()