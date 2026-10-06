"""
Exports the Power BI model from DuckDB: two fact tables, two dimensions and
three pre-aggregated tables.
"""

from pathlib import Path

import duckdb

# Paths resolve from this file rather than the working directory, so the script
# behaves the same from the project root, from analysis/ and from an IDE.
ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "warehouse" / "logistics_pulse.duckdb"
OUT_DIR = ROOT / "data" / "powerbi"

# Delivered orders with a known outcome are the entire scope of the analysis, so
# the filter belongs in the fact table, not in the report. No measure can then
# count an order that never arrived.
SCOPE = "o.order_status = 'delivered' AND o.is_late IS NOT NULL"

# Reference data, not observed data: the dataset carries only the two-letter
# code. Full names are here because Power BI's map geocodes a name far more
# reliably than a code, and because "Rio de Janeiro" belongs in a tooltip.
BRAZIL_STATES = [
    ("AC", "Acre", "North"),
    ("AL", "Alagoas", "Northeast"),
    ("AM", "Amazonas", "North"),
    ("AP", "Amapa", "North"),
    ("BA", "Bahia", "Northeast"),
    ("CE", "Ceara", "Northeast"),
    ("DF", "Distrito Federal", "Central-West"),
    ("ES", "Espirito Santo", "Southeast"),
    ("GO", "Goias", "Central-West"),
    ("MA", "Maranhao", "Northeast"),
    ("MG", "Minas Gerais", "Southeast"),
    ("MS", "Mato Grosso do Sul", "Central-West"),
    ("MT", "Mato Grosso", "Central-West"),
    ("PA", "Para", "North"),
    ("PB", "Paraiba", "Northeast"),
    ("PE", "Pernambuco", "Northeast"),
    ("PI", "Piaui", "Northeast"),
    ("PR", "Parana", "South"),
    ("RJ", "Rio de Janeiro", "Southeast"),
    ("RN", "Rio Grande do Norte", "Northeast"),
    ("RO", "Rondonia", "North"),
    ("RR", "Roraima", "North"),
    ("RS", "Rio Grande do Sul", "South"),
    ("SC", "Santa Catarina", "South"),
    ("SE", "Sergipe", "Northeast"),
    ("SP", "Sao Paulo", "Southeast"),
    ("TO", "Tocantins", "North"),
]

# One row per order. Distance is aggregated to the order with MAX before the
# join, the same way every distance query in the notebook does it - joining
# order_items directly would count a three-item order three times.
#
# The bucket columns are paired with an integer, because Power BI sorts text
# alphabetically: without it the axis reads 1-3, 15+, 4-7, 8-14.
FACT_ORDERS = f"""
WITH order_distance AS (
    SELECT order_id, MAX(distance_km) AS distance_km
    FROM order_items
    GROUP BY order_id
)
SELECT
    o.order_id,
    CAST(o.order_purchase_timestamp AS DATE)            AS order_date,
    c.customer_state,
    o.is_late,
    o.delay_days,
    o.approval_hours,
    o.preparation_hours,
    o.transit_hours,
    date_diff('hour', o.order_purchase_timestamp,
              o.order_delivered_customer_date) / 24.0   AS actual_days,
    date_diff('hour', o.order_purchase_timestamp,
              o.order_estimated_delivery_date) / 24.0   AS promised_days,
    d.distance_km,
    CASE
        WHEN d.distance_km IS NULL  THEN NULL
        WHEN d.distance_km < 100    THEN 'under 100 km'
        WHEN d.distance_km < 300    THEN '100-300 km'
        WHEN d.distance_km < 700    THEN '300-700 km'
        WHEN d.distance_km < 1500   THEN '700-1500 km'
        ELSE                             'over 1500 km'
    END                                                 AS distance_bucket,
    CASE
        WHEN d.distance_km IS NULL  THEN NULL
        WHEN d.distance_km < 100    THEN 1
        WHEN d.distance_km < 300    THEN 2
        WHEN d.distance_km < 700    THEN 3
        WHEN d.distance_km < 1500   THEN 4
        ELSE                             5
    END                                                 AS distance_bucket_order,
    CASE
        WHEN o.delay_days IS NULL   THEN NULL
        WHEN o.delay_days <= 0      THEN 'on time or early'
        WHEN o.delay_days <= 3      THEN '1-3 days late'
        WHEN o.delay_days <= 7      THEN '4-7 days late'
        WHEN o.delay_days <= 14     THEN '8-14 days late'
        ELSE                             '15+ days late'
    END                                                 AS delay_bucket,
    CASE
        WHEN o.delay_days IS NULL   THEN NULL
        WHEN o.delay_days <= 0      THEN 1
        WHEN o.delay_days <= 3      THEN 2
        WHEN o.delay_days <= 7      THEN 3
        WHEN o.delay_days <= 14     THEN 4
        ELSE                             5
    END                                                 AS delay_bucket_order,
    r.review_score
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
LEFT JOIN order_distance d ON o.order_id = d.order_id
LEFT JOIN reviews r ON o.order_id = r.order_id
WHERE {SCOPE}
"""

# One row per order per stage. The three stage columns are unpivoted because a
# Power BI axis reads rows, not columns: with the wide shape there is no field
# to put on the category axis of the stage chart.
#
# Written as UNION ALL rather than UNPIVOT so that each stage carries its own
# sort order, and so the stage names are the ones that appear on the chart.
FACT_STAGE_HOURS = f"""
SELECT
    o.order_id,
    CAST(o.order_purchase_timestamp AS DATE) AS order_date,
    c.customer_state,
    o.is_late,
    'Payment approval'                       AS stage,
    1                                        AS stage_order,
    o.approval_hours                         AS hours
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE {SCOPE} AND o.approval_hours IS NOT NULL

UNION ALL

SELECT
    o.order_id,
    CAST(o.order_purchase_timestamp AS DATE),
    c.customer_state,
    o.is_late,
    'Preparation',
    2,
    o.preparation_hours
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE {SCOPE} AND o.preparation_hours IS NOT NULL

UNION ALL

SELECT
    o.order_id,
    CAST(o.order_purchase_timestamp AS DATE),
    c.customer_state,
    o.is_late,
    'Transit',
    3,
    o.transit_hours
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE {SCOPE} AND o.transit_hours IS NOT NULL
"""

# Query 8b. Six rows, a fixed window, and the expected count needs the rest of
# the country's rate per month with Rio removed - the same reasoning as alerts:
# nobody slices it, and SQL states it plainly where DAX would not.
RIO_EXCESS = f"""
WITH monthly AS (
    SELECT
        date_trunc('month', o.order_purchase_timestamp)               AS month,
        COUNT(*) FILTER (WHERE c.customer_state = 'RJ')               AS rj_orders,
        COUNT(*) FILTER (WHERE c.customer_state = 'RJ' AND o.is_late) AS rj_late,
        COUNT(*) FILTER (WHERE c.customer_state <> 'RJ' AND o.is_late)
            / COUNT(*) FILTER (WHERE c.customer_state <> 'RJ')        AS rest_late_rate
    FROM orders o
    JOIN customers c ON o.customer_id = c.customer_id
    WHERE {SCOPE}
      AND o.order_purchase_timestamp >= '2017-10-01'
      AND o.order_purchase_timestamp < '2018-04-01'
    GROUP BY month
)
SELECT
    CAST(month AS DATE)                            AS month,
    rj_orders,
    rj_late,
    ROUND(rj_orders * rest_late_rate, 0)           AS expected_late,
    ROUND(rj_late - rj_orders * rest_late_rate, 0) AS excess_late
FROM monthly
ORDER BY month
"""

# A date table has to be gapless, so it is generated rather than selected from
# the orders. Marking it as the date table in Power BI is what stops months
# sorting alphabetically.
DIM_DATE = f"""
WITH bounds AS (
    SELECT
        MIN(CAST(o.order_purchase_timestamp AS DATE)) AS first_day,
        MAX(CAST(o.order_purchase_timestamp AS DATE)) AS last_day
    FROM orders o
    WHERE {SCOPE}
)
SELECT
    CAST(d AS DATE)                      AS date,
    year(d)                              AS year,
    month(d)                              AS month_number,
    strftime(d, '%b %Y')                 AS month_label,
    year(d) * 100 + month(d)             AS month_sort
FROM bounds, generate_series(first_day, last_day, INTERVAL 1 DAY) AS t(d)
"""

STATE_VALUES = ", ".join(f"('{code}', '{name}', '{region}')" for code, name, region in BRAZIL_STATES)

DIM_STATE = f"""
SELECT *
FROM (VALUES {STATE_VALUES}) AS t(state_code, state_name, region)
"""

# Seller sits at item grain, not order grain, so it cannot be a column on the
# fact table - one order can carry items from several sellers. This is the same
# reason the notebook counts DISTINCT order_id here.
SELLER_RATES = f"""
SELECT
    ot.seller_id,
    COUNT(DISTINCT o.order_id)                          AS orders,
    COUNT(DISTINCT o.order_id) FILTER (WHERE o.is_late) AS late_orders,
    ROUND(COUNT(DISTINCT o.order_id) FILTER (WHERE o.is_late)
          / COUNT(DISTINCT o.order_id) * 100, 2)        AS late_pct
FROM orders o
JOIN order_items ot ON o.order_id = ot.order_id
WHERE {SCOPE}
GROUP BY ot.seller_id
HAVING COUNT(DISTINCT o.order_id) >= 100
ORDER BY late_pct DESC
"""

# Query 8c, unchanged. The rule needs two consecutive months, which DAX handles
# badly and SQL handles plainly, and the result is a list of events rather than
# a number anyone would want to slice.
ALERTS = f"""
WITH state_month AS (
    SELECT
        date_trunc('month', o.order_purchase_timestamp) AS month,
        c.customer_state                                AS state,
        COUNT(*)                                        AS orders,
        COUNT(*) FILTER (WHERE o.is_late)               AS late_orders
    FROM orders o
    JOIN customers c ON o.customer_id = c.customer_id
    WHERE {SCOPE}
      AND o.order_purchase_timestamp >= '2017-01-01'
    GROUP BY month, state
),

country_month AS (
    SELECT month, SUM(orders) AS orders, SUM(late_orders) AS late_orders
    FROM state_month
    GROUP BY month
),

compared AS (
    SELECT
        s.month,
        s.state,
        s.orders,
        s.late_orders / s.orders             AS state_rate,
        (c.late_orders - s.late_orders)
            / NULLIF(c.orders - s.orders, 0) AS rest_rate
    FROM state_month s
    JOIN country_month c USING (month)
    WHERE s.orders >= 100
)

SELECT
    CAST(month AS DATE)                         AS month,
    state,
    orders,
    ROUND(state_rate * 100, 1)                  AS state_pct,
    ROUND(rest_rate * 100, 1)                   AS rest_pct,
    ROUND(state_rate / NULLIF(rest_rate, 0), 1) AS ratio,
    CASE
        WHEN state_rate >= 0.15 AND state_rate >= 2 * rest_rate THEN 'both'
        WHEN state_rate >= 0.15                                 THEN 'absolute'
        ELSE                                                         'relative'
    END                                         AS triggered_by
FROM compared
WHERE state_rate >= 2 * rest_rate
   OR (state_rate >= 0.15 AND state_rate >= 1.5 * rest_rate)
ORDER BY month, state
"""

# seller_rates, alerts and rio_excess stay DISCONNECTED in Power BI - no
# relationship to dim_date or dim_state. Each is a finished cut at its own
# grain, and relating alerts.month to dim_date[date] would match only the first
# of each month, so a date slicer would quietly empty the page.
EXPORTS = {
    "fact_orders": FACT_ORDERS,
    "fact_stage_hours": FACT_STAGE_HOURS,
    "dim_date": DIM_DATE,
    "dim_state": DIM_STATE,
    "seller_rates": SELLER_RATES,
    "alerts": ALERTS,
    "rio_excess": RIO_EXCESS,
}


def export(con: duckdb.DuckDBPyConnection, name: str, query: str) -> int:
    """Write one query to parquet and return the row count."""
    path = OUT_DIR / f"{name}.parquet"
    con.execute(f"COPY ({query}) TO '{path}' (FORMAT PARQUET)")
    return con.execute(f"SELECT count(*) FROM '{path}'").fetchone()[0]


def check_fact_grain(con: duckdb.DuckDBPyConnection, fact_rows: int) -> None:
    """Fail if the fact table gained rows from its joins.

    reviews is one row per order today, but a LEFT JOIN that starts fanning out
    would inflate every rate on the dashboard without raising an error.
    """
    expected = con.execute(f"SELECT count(*) FROM orders o WHERE {SCOPE}").fetchone()[0]
    if fact_rows != expected:
        raise AssertionError(
            f"fact_orders has {fact_rows} rows, expected {expected} - a join is duplicating orders"
        )


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(DB_PATH, read_only=True)

    counts = {name: export(con, name, query) for name, query in EXPORTS.items()}
    check_fact_grain(con, counts["fact_orders"])

    for name, rows in counts.items():
        print(f"{name}: {rows}")

    con.close()


if __name__ == "__main__":
    main()
