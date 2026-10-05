-- Logistics Pulse - KPI queries
-- Every query in notebooks/02_sql_analysis.ipynb, in the order it appears.
-- Run against data/warehouse/logistics_pulse.duckdb.

-- ----------------------------------------------------------------------
-- 1. Baseline - what is the late delivery rate?
-- ----------------------------------------------------------------------

SELECT
    COUNT(*) AS orders,
    COUNT(*) FILTER (WHERE is_late) AS late_orders,
    ROUND(COUNT(*) FILTER (WHERE is_late) / COUNT(*) * 100, 2) AS late_rate_pct
FROM orders
WHERE is_late IS NOT NULL
AND order_status = 'delivered';

-- ----------------------------------------------------------------------
-- 2. Which stage creates the delay?
-- ----------------------------------------------------------------------

SELECT
    ROUND(MEDIAN(approval_hours) FILTER (WHERE is_late) ,1) AS approval_late,
    ROUND(MEDIAN(approval_hours) FILTER (WHERE NOT is_late),1) AS approval_ontime,
    ROUND(MEDIAN(preparation_hours) FILTER (WHERE is_late),1) AS preparation_late,
    ROUND(MEDIAN(preparation_hours) FILTER (WHERE NOT is_late),1) AS preparation_ontime,
    ROUND(MEDIAN(transit_hours) FILTER (WHERE is_late),1) AS transit_late,
    ROUND(MEDIAN(transit_hours) FILTER (WHERE NOT is_late),1) AS transit_ontime
FROM orders
WHERE is_late IS NOT NULL
AND order_status = 'delivered';

-- ----------------------------------------------------------------------
-- 3a. Late rate by customer region
-- ----------------------------------------------------------------------

SELECT
    c.customer_state                  AS state,
    COUNT(*)                          AS orders,
    COUNT(*) FILTER (WHERE o.is_late) AS late_orders,
    ROUND(COUNT(*) FILTER (WHERE o.is_late) / COUNT(*) * 100, 2) AS late_rate_pct,
    ROUND(COUNT(*) FILTER (WHERE o.is_late)
          / SUM(COUNT(*) FILTER (WHERE o.is_late)) OVER () * 100, 2) AS share_of_late_pct
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE o.is_late IS NOT NULL
AND o.order_status = 'delivered'
GROUP BY c.customer_state
ORDER BY late_orders DESC;

-- ----------------------------------------------------------------------
-- 3b. Late rate by seller - the largest sellers first
-- ----------------------------------------------------------------------

SELECT
    ot.seller_id,
    COUNT(DISTINCT o.order_id)                  AS orders,
    COUNT(DISTINCT o.order_id) FILTER (WHERE o.is_late)        AS late_orders,
    ROUND(COUNT(DISTINCT o.order_id) FILTER (WHERE o.is_late) / COUNT(DISTINCT o.order_id) * 100, 2) AS late_pct
FROM orders o
JOIN order_items ot ON o.order_id = ot.order_id
WHERE o.is_late IS NOT NULL
AND o.order_status = 'delivered'
GROUP BY ot.seller_id
ORDER BY late_orders DESC
LIMIT 20;

-- ----------------------------------------------------------------------
-- 3b. Late rate by seller - by rate, with a volume floor
-- ----------------------------------------------------------------------

SELECT
    ot.seller_id,
    COUNT(DISTINCT o.order_id)                            AS orders,
    COUNT(DISTINCT o.order_id) FILTER (WHERE o.is_late)   AS late_orders,
    ROUND(COUNT(DISTINCT o.order_id) FILTER (WHERE o.is_late)
          / COUNT(DISTINCT o.order_id) * 100, 2)          AS late_pct
FROM orders o
JOIN order_items ot ON o.order_id = ot.order_id
WHERE o.is_late IS NOT NULL
  AND o.order_status = 'delivered'
GROUP BY ot.seller_id
HAVING COUNT(DISTINCT o.order_id) >= 100
ORDER BY late_pct DESC
LIMIT 15;

-- ----------------------------------------------------------------------
-- 3c. Late rate by product category
-- ----------------------------------------------------------------------

SELECT
    p.product_category                                     AS category,
    COUNT(DISTINCT o.order_id)                             AS orders,
    COUNT(DISTINCT o.order_id) FILTER (WHERE o.is_late)    AS late_orders,
    ROUND(COUNT(DISTINCT o.order_id) FILTER (WHERE o.is_late) / COUNT(DISTINCT o.order_id) * 100, 2) AS late_pct
FROM orders o
JOIN order_items ot ON o.order_id = ot.order_id
JOIN products p ON p.product_id = ot.product_id
WHERE o.is_late IS NOT NULL
AND o.order_status = 'delivered'
GROUP BY p.product_category
ORDER BY late_orders DESC
LIMIT 15;

-- ----------------------------------------------------------------------
-- 4a. Late rate by distance band
-- ----------------------------------------------------------------------

WITH order_distance AS (
    SELECT
        o.order_id,
        o.is_late,
        MAX(ot.distance_km) AS distance_km
    FROM orders o
    JOIN order_items ot ON o.order_id = ot.order_id
    WHERE o.is_late IS NOT NULL
    AND o.order_status = 'delivered'
    GROUP BY o.order_id, o.is_late
    )
SELECT
    CASE
        WHEN distance_km < 100 THEN 'under 100 km'
        WHEN distance_km < 300 THEN '100-300 km'
        WHEN distance_km < 700 THEN '300-700 km'
        WHEN distance_km < 1500 THEN '700-1500 km'
        ELSE 'over 1500 km'
        END AS distance_bucket,
    COUNT(*)                AS orders,
    COUNT(order_id) FILTER (WHERE is_late)        AS late_orders,
    ROUND(COUNT(order_id) FILTER (WHERE is_late) / COUNT(*) * 100, 1) AS late_pct
FROM order_distance
WHERE distance_km IS NOT NULL
GROUP BY distance_bucket
ORDER BY MIN(distance_km);

-- ----------------------------------------------------------------------
-- 4b. Median distance by state
-- ----------------------------------------------------------------------

WITH order_distance AS (
    SELECT
        o.order_id,
        c.customer_state,
        MAX(ot.distance_km) AS distance_km
    FROM orders o
    JOIN order_items ot ON o.order_id = ot.order_id
    JOIN customers c ON o.customer_id = c.customer_id
    WHERE o.is_late IS NOT NULL
      AND o.order_status = 'delivered'
    GROUP BY o.order_id, c.customer_state
)
SELECT
    customer_state,
    COUNT(*)                        AS orders,
    ROUND(MEDIAN(distance_km), 0)   AS median_distance_km
FROM order_distance
WHERE distance_km IS NOT NULL
GROUP BY customer_state
ORDER BY orders DESC
LIMIT 10;

-- ----------------------------------------------------------------------
-- 5a. Late rate by month
-- ----------------------------------------------------------------------

SELECT
    date_trunc('month', order_purchase_timestamp)         AS month,
    COUNT(*)                                              AS orders,
    COUNT(*) FILTER (WHERE is_late)                       AS late_orders,
    ROUND(COUNT(*) FILTER (WHERE is_late) / COUNT(*) * 100, 2) AS late_rate_pct
FROM orders
WHERE is_late IS NOT NULL
AND order_status = 'delivered'
GROUP BY month
ORDER BY month;

-- ----------------------------------------------------------------------
-- 5b. Promised time against actual time
-- ----------------------------------------------------------------------

SELECT
    date_trunc('month', order_purchase_timestamp)                      AS month,
    ROUND(MEDIAN(date_diff('hour', order_purchase_timestamp,
                 order_delivered_customer_date) / 24.0), 1)            AS actual_days,
    ROUND(MEDIAN(date_diff('hour', order_purchase_timestamp,
                 order_estimated_delivery_date) / 24.0), 1)            AS promised_days,
    ROUND(promised_days - actual_days, 1)                              AS gap_days
FROM orders
WHERE is_late IS NOT NULL
  AND order_status = 'delivered'
  AND order_purchase_timestamp >= '2017-01-01'
GROUP BY month
ORDER BY month;

-- ----------------------------------------------------------------------
-- 5c. Four states month by month
-- ----------------------------------------------------------------------

SELECT
    date_trunc('month', o.order_purchase_timestamp)                 AS month,
    ROUND(COUNT(*) FILTER (WHERE c.customer_state = 'RJ' AND o.is_late)
          / COUNT(*) FILTER (WHERE c.customer_state = 'RJ') * 100, 1)  AS rj,
    ROUND(COUNT(*) FILTER (WHERE c.customer_state = 'BA' AND o.is_late)
          / COUNT(*) FILTER (WHERE c.customer_state = 'BA') * 100, 1)  AS ba,
    ROUND(COUNT(*) FILTER (WHERE c.customer_state = 'SP' AND o.is_late)
          / COUNT(*) FILTER (WHERE c.customer_state = 'SP') * 100, 1)  AS sp,
    ROUND(COUNT(*) FILTER (WHERE c.customer_state = 'MG' AND o.is_late)
          / COUNT(*) FILTER (WHERE c.customer_state = 'MG') * 100, 1)  AS mg
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE o.order_status = 'delivered'
  AND o.is_late IS NOT NULL
  AND o.order_purchase_timestamp >= '2017-01-01'
GROUP BY month
ORDER BY month;

-- ----------------------------------------------------------------------
-- 6a. Rio against the rest of the country
-- ----------------------------------------------------------------------

SELECT
    date_trunc('month', o.order_purchase_timestamp)                    AS month,
    COUNT(*) FILTER (WHERE c.customer_state = 'RJ')                    AS rj_orders,
    ROUND(COUNT(*) FILTER (WHERE c.customer_state = 'RJ' AND o.is_late)
          / COUNT(*) FILTER (WHERE c.customer_state = 'RJ') * 100, 2)  AS rj_late_pct,
    COUNT(*) FILTER (WHERE c.customer_state <> 'RJ')                   AS rest_orders,
    ROUND(COUNT(*) FILTER (WHERE c.customer_state <> 'RJ' AND o.is_late)
          / COUNT(*) FILTER (WHERE c.customer_state <> 'RJ') * 100, 2) AS rest_late_pct,
    ROUND(rj_late_pct / rest_late_pct, 1)                              AS rj_vs_rest
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE o.is_late IS NOT NULL
  AND o.order_status = 'delivered'
  AND o.order_purchase_timestamp >= '2017-01-01'
GROUP BY month
ORDER BY month;

-- ----------------------------------------------------------------------
-- 6b. States compared at the same distance
-- ----------------------------------------------------------------------

WITH order_distance AS (
    SELECT order_id, MAX(distance_km) AS distance_km
    FROM order_items
    GROUP BY order_id
)

SELECT
    c.customer_state,
    COUNT(*)                                                     AS orders,
    COUNT(*) FILTER (WHERE o.is_late)                            AS late_orders,
    ROUND(COUNT(*) FILTER (WHERE o.is_late) / COUNT(*) * 100, 2) AS late_rate_pct,
    ROUND(MEDIAN(d.distance_km), 0)                              AS median_distance_km
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
JOIN order_distance d ON o.order_id = d.order_id
WHERE o.order_status = 'delivered'
  AND o.is_late IS NOT NULL
  AND d.distance_km BETWEEN 200 AND 600
  AND o.order_purchase_timestamp >= '2017-10-01'
  AND o.order_purchase_timestamp < '2018-04-01'
GROUP BY c.customer_state
HAVING COUNT(*) >= 200
ORDER BY late_rate_pct DESC;

-- ----------------------------------------------------------------------
-- 6c. The size of the Rio episode
-- ----------------------------------------------------------------------

WITH monthly AS (
    SELECT
        date_trunc('month', o.order_purchase_timestamp)                AS month,
        COUNT(*) FILTER (WHERE c.customer_state = 'RJ')                AS rj_orders,
        COUNT(*) FILTER (WHERE c.customer_state = 'RJ' AND o.is_late)  AS rj_late,
        COUNT(*) FILTER (WHERE c.customer_state <> 'RJ' AND o.is_late)
            / COUNT(*) FILTER (WHERE c.customer_state <> 'RJ')         AS rest_late_rate
    FROM orders o
    JOIN customers c ON o.customer_id = c.customer_id
    WHERE o.order_status = 'delivered'
      AND o.is_late IS NOT NULL
      AND o.order_purchase_timestamp >= '2017-10-01'
      AND o.order_purchase_timestamp < '2018-04-01'
    GROUP BY month
)

SELECT
    SUM(rj_orders)                                            AS rj_orders,
    SUM(rj_late)                                              AS rj_late,
    ROUND(SUM(rj_orders * rest_late_rate), 0)                 AS expected_late,
    ROUND(SUM(rj_late) - SUM(rj_orders * rest_late_rate), 0)  AS excess_late,
    ROUND((SUM(rj_late) - SUM(rj_orders * rest_late_rate))
          / (SELECT COUNT(*) FILTER (WHERE is_late)
             FROM orders
             WHERE order_status = 'delivered' AND is_late IS NOT NULL)
          * 100, 1)                                           AS pct_of_all_late
FROM monthly;

-- ----------------------------------------------------------------------
-- 7. Review score by length of delay
-- ----------------------------------------------------------------------

SELECT
    CASE
        WHEN o.delay_days <= 0  THEN 'on time or early'
        WHEN o.delay_days <= 3  THEN '1-3 days late'
        WHEN o.delay_days <= 7  THEN '4-7 days late'
        WHEN o.delay_days <= 14 THEN '8-14 days late'
        ELSE '15+ days late'
    END                                                            AS delay_bucket,
    COUNT(*)                                                       AS orders,
    ROUND(AVG(r.review_score), 2)                                  AS avg_score,
    ROUND(COUNT(*) FILTER (WHERE r.review_score = 1)
          / COUNT(*) * 100, 1)                                     AS one_star_pct
FROM orders o
JOIN reviews r ON o.order_id = r.order_id
WHERE o.order_status = 'delivered'
  AND o.is_late IS NOT NULL
GROUP BY delay_bucket
ORDER BY MIN(o.delay_days);

-- ----------------------------------------------------------------------
-- 8a. What a late delivery cost in Rio
-- ----------------------------------------------------------------------

SELECT
    o.is_late,
    COUNT(*)                      AS orders,
    ROUND(AVG(r.review_score), 2) AS avg_score
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
JOIN reviews r  ON o.order_id = r.order_id
WHERE o.order_status = 'delivered'
  AND o.is_late IS NOT NULL
  AND c.customer_state = 'RJ'
  AND o.order_purchase_timestamp >= '2017-10-01'
  AND o.order_purchase_timestamp < '2018-04-01'
GROUP BY o.is_late;

-- ----------------------------------------------------------------------
-- 8b. The Rio excess month by month
-- ----------------------------------------------------------------------

WITH monthly AS (
    SELECT
        date_trunc('month', o.order_purchase_timestamp)                AS month,
        COUNT(*) FILTER (WHERE c.customer_state = 'RJ')                AS rj_orders,
        COUNT(*) FILTER (WHERE c.customer_state = 'RJ' AND o.is_late)  AS rj_late,
        COUNT(*) FILTER (WHERE c.customer_state <> 'RJ' AND o.is_late)
            / COUNT(*) FILTER (WHERE c.customer_state <> 'RJ')         AS rest_late_rate
    FROM orders o
    JOIN customers c ON o.customer_id = c.customer_id
    WHERE o.order_status = 'delivered'
      AND o.is_late IS NOT NULL
      AND o.order_purchase_timestamp >= '2017-10-01'
      AND o.order_purchase_timestamp < '2018-04-01'
    GROUP BY month
)

SELECT
    month,
    rj_orders,
    rj_late,
    ROUND(rj_orders * rest_late_rate, 0)            AS expected_late,
    ROUND(rj_late - rj_orders * rest_late_rate, 0)  AS excess_late
FROM monthly
ORDER BY month;

-- ----------------------------------------------------------------------
-- 8c. The rule applied to every state
-- ----------------------------------------------------------------------

WITH state_month AS (
    SELECT
        date_trunc('month', o.order_purchase_timestamp) AS month,
        c.customer_state                                AS state,
        COUNT(*)                                        AS orders,
        COUNT(*) FILTER (WHERE o.is_late)               AS late_orders
    FROM orders o
    JOIN customers c ON o.customer_id = c.customer_id
    WHERE o.order_status = 'delivered'
      AND o.is_late IS NOT NULL
      AND o.order_purchase_timestamp >= '2017-01-01'
    GROUP BY month, state
),

country_month AS (
    SELECT
        month,
        SUM(orders)      AS orders,
        SUM(late_orders) AS late_orders
    FROM state_month
    GROUP BY month
),

compared AS (
    SELECT
        s.month,
        s.state,
        s.orders,
        s.late_orders / s.orders                          AS state_rate,
        (c.late_orders - s.late_orders)
            / NULLIF(c.orders - s.orders, 0)              AS rest_rate
    FROM state_month s
    JOIN country_month c USING (month)
    WHERE s.orders >= 100
)

SELECT
    month,
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
ORDER BY month, state;
