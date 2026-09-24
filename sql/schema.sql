-- Logistics Pulse - DuckDB schema
-- Table order matters: a table comes after every table it points to.
-- Built from data/processed/, not from the raw CSVs.

CREATE TABLE customers (
    customer_id              VARCHAR PRIMARY KEY,
    customer_unique_id       VARCHAR NOT NULL,
    customer_zip_code_prefix INTEGER NOT NULL,
    customer_city            VARCHAR NOT NULL,
    customer_state           VARCHAR NOT NULL
);

CREATE TABLE sellers (
    seller_id              VARCHAR PRIMARY KEY,
    seller_zip_code_prefix INTEGER NOT NULL,
    seller_city            VARCHAR NOT NULL,
    seller_state           VARCHAR NOT NULL
);

CREATE TABLE products (
    product_id       VARCHAR PRIMARY KEY,
    product_category VARCHAR
);

-- The zip code columns do not point here. 157 customer and 7 seller zip
-- prefixes have no coordinates, and a foreign key would reject those rows.
CREATE TABLE geolocation (
    geolocation_zip_code_prefix INTEGER PRIMARY KEY,
    geolocation_lat             DOUBLE NOT NULL,
    geolocation_lng             DOUBLE NOT NULL
);

-- The five source timestamps stay. Every column below them is calculated
-- from these dates, so keeping them makes the numbers easy to check in SQL.
CREATE TABLE orders (
    order_id                      VARCHAR PRIMARY KEY,
    customer_id                   VARCHAR   NOT NULL REFERENCES customers (customer_id),
    order_status                  VARCHAR   NOT NULL,
    order_purchase_timestamp      TIMESTAMP NOT NULL,
    order_approved_at             TIMESTAMP,
    order_delivered_carrier_date  TIMESTAMP,
    order_delivered_customer_date TIMESTAMP,
    order_estimated_delivery_date TIMESTAMP NOT NULL,
    delay_days                    INTEGER,
    is_late                       BOOLEAN,
    approval_hours                DOUBLE CHECK (approval_hours >= 0),
    preparation_hours             DOUBLE CHECK (preparation_hours >= 0),
    transit_hours                 DOUBLE CHECK (transit_hours >= 0),
    carrier_before_approved       BOOLEAN,
    delivered_before_carrier      BOOLEAN
);

-- order_id is the primary key and a foreign key at once: one review per
-- order, checked by the database and not only by the cleaning script.
CREATE TABLE reviews (
    order_id     VARCHAR PRIMARY KEY REFERENCES orders (order_id),
    review_score INTEGER NOT NULL CHECK (review_score BETWEEN 1 AND 5)
);

-- distance_km comes from a second parquet file, joined in by load_data.py.
-- It has the same grain and the same key, so it belongs in this table.
CREATE TABLE order_items (
    order_id                 VARCHAR   NOT NULL REFERENCES orders (order_id),
    order_item_id            INTEGER   NOT NULL,
    product_id               VARCHAR   NOT NULL REFERENCES products (product_id),
    seller_id                VARCHAR   NOT NULL REFERENCES sellers (seller_id),
    shipping_limit_date      TIMESTAMP NOT NULL,
    price                    DOUBLE    NOT NULL,
    freight_value            DOUBLE    NOT NULL,
    missed_shipping_deadline BOOLEAN,
    distance_km              DOUBLE,
    PRIMARY KEY (order_id, order_item_id)
);