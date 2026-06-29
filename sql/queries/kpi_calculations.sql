-- ── KPI 1: MONTHLY REVENUE TREND ─────────────────────────
SELECT
    purchase_year,
    purchase_month,
    COUNT(DISTINCT order_id) AS total_orders,
    ROUND(SUM(gross_revenue)::numeric, 2) AS gross_revenue,
    ROUND(AVG(gross_revenue)::numeric, 2) AS avg_order_value,
    COUNT(DISTINCT customer_id) AS unique_customers
FROM fact_orders
GROUP BY purchase_year, purchase_month
ORDER BY purchase_year, purchase_month;

-- ── KPI 2: MONTH OVER MONTH GROWTH ───────────────────────
WITH monthly AS (
    SELECT
        purchase_year,
        purchase_month,
        SUM(gross_revenue) AS revenue
    FROM fact_orders
    GROUP BY purchase_year, purchase_month
)
SELECT
    *,
    LAG(revenue) OVER (ORDER BY purchase_year, purchase_month) AS prev_month,
    ROUND(
        CAST(
            (revenue - LAG(revenue) OVER (ORDER BY purchase_year, purchase_month)) /
            NULLIF(LAG(revenue) OVER (ORDER BY purchase_year, purchase_month), 0) * 100
        AS numeric)
    , 2) AS mom_growth_pct
FROM monthly
ORDER BY purchase_year, purchase_month;

-- ── KPI 3: CUSTOMER SEGMENTS BY VALUE ────────────────────
WITH customer_stats AS (
    SELECT
        customer_id,
        COUNT(order_id) AS total_orders,
        SUM(gross_revenue) AS total_revenue
    FROM fact_orders
    GROUP BY customer_id
)
SELECT
    CASE
        WHEN total_revenue > 500 THEN 'High Value'
        WHEN total_revenue > 200 THEN 'Mid Value'
        ELSE 'Low Value'
    END AS customer_segment,
    COUNT(*) AS customer_count,
    ROUND(AVG(total_revenue)::numeric, 2) AS avg_revenue,
    ROUND(AVG(total_orders)::numeric, 2) AS avg_orders
FROM customer_stats
GROUP BY customer_segment
ORDER BY avg_revenue DESC;

-- ── KPI 4: DELIVERY PERFORMANCE ──────────────────────────
SELECT
    purchase_year,
    purchase_month,
    COUNT(*) AS total_deliveries,
    ROUND(AVG(delivery_days)::numeric, 1) AS avg_delivery_days,
    SUM(is_late) AS late_deliveries,
    ROUND(SUM(is_late)::numeric / COUNT(*) * 100, 2) AS late_rate_pct
FROM fact_orders
WHERE delivery_days IS NOT NULL
GROUP BY purchase_year, purchase_month
ORDER BY purchase_year, purchase_month;

-- ── KPI 5: REVENUE BY DAY OF WEEK ────────────────────────
SELECT
    CASE purchase_dayofweek
        WHEN 0 THEN 'Sunday'
        WHEN 1 THEN 'Monday'
        WHEN 2 THEN 'Tuesday'
        WHEN 3 THEN 'Wednesday'
        WHEN 4 THEN 'Thursday'
        WHEN 5 THEN 'Friday'
        WHEN 6 THEN 'Saturday'
    END AS day_name,
    COUNT(order_id) AS total_orders,
    ROUND(SUM(gross_revenue)::numeric, 2) AS revenue,
    ROUND(AVG(gross_revenue)::numeric, 2) AS avg_order_value
FROM fact_orders
GROUP BY purchase_dayofweek
ORDER BY purchase_dayofweek;

-- ── KPI 6: TOP CUSTOMERS BY REVENUE ──────────────────────
SELECT
    f.customer_id,
    COUNT(DISTINCT f.order_id) AS total_orders,
    ROUND(SUM(f.gross_revenue)::numeric, 2) AS total_revenue,
    ROUND(AVG(f.gross_revenue)::numeric, 2) AS avg_order_value,
    ROUND(AVG(f.delivery_days)::numeric, 1) AS avg_delivery_days,
    ROUND(AVG(r.review_score)::numeric, 2) AS avg_rating
FROM fact_orders f
LEFT JOIN dim_reviews r ON f.order_id = r.order_id
GROUP BY f.customer_id
ORDER BY total_revenue DESC
LIMIT 20;

-- ── KPI 7: OVERALL BUSINESS SUMMARY ──────────────────────
SELECT
    COUNT(DISTINCT f.order_id) AS total_orders,
    COUNT(DISTINCT f.customer_id) AS total_customers,
    ROUND(SUM(f.gross_revenue)::numeric, 2) AS total_revenue,
    ROUND(AVG(f.gross_revenue)::numeric, 2) AS avg_order_value,
    ROUND(AVG(f.delivery_days)::numeric, 1) AS avg_delivery_days,
    SUM(f.is_late) AS total_late_orders,
    ROUND(AVG(r.review_score)::numeric, 2) AS avg_review_score
FROM fact_orders f
LEFT JOIN dim_reviews r ON f.order_id = r.order_id;