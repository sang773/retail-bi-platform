-- ── TIME DIMENSION ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS dim_time AS
SELECT DISTINCT
    DATE(order_purchase_timestamp) AS date_key,
    EXTRACT(YEAR FROM order_purchase_timestamp) AS year,
    EXTRACT(QUARTER FROM order_purchase_timestamp) AS quarter,
    EXTRACT(MONTH FROM order_purchase_timestamp) AS month,
    TO_CHAR(order_purchase_timestamp, 'Month') AS month_name,
    EXTRACT(WEEK FROM order_purchase_timestamp) AS week_of_year,
    EXTRACT(DOW FROM order_purchase_timestamp) AS day_of_week,
    CASE
        WHEN EXTRACT(DOW FROM order_purchase_timestamp) IN (0,6)
        THEN TRUE ELSE FALSE
    END AS is_weekend
FROM fact_orders
WHERE order_purchase_timestamp IS NOT NULL;

-- ── PRIMARY KEYS ─────────────────────────────────────────
ALTER TABLE fact_orders ADD PRIMARY KEY (order_id);
ALTER TABLE dim_customers ADD PRIMARY KEY (customer_id);
ALTER TABLE dim_products ADD PRIMARY KEY (product_id);

-- ── CONFIRM ALL TABLES EXIST ──────────────────────────────
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;