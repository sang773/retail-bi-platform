-- Month-over-month revenue growth
WITH monthly_revenue AS (
    SELECT 
        purchase_year,
        purchase_month,
        SUM(gross_revenue) AS revenue
    FROM fact_orders
    GROUP BY purchase_year, purchase_month
)
SELECT 
    *,
    LAG(revenue) OVER (ORDER BY purchase_year, purchase_month) AS prev_month_revenue,
    ROUND(
        (revenue - LAG(revenue) OVER (ORDER BY purchase_year, purchase_month)) /
        LAG(revenue) OVER (ORDER BY purchase_year, purchase_month) * 100, 2
    ) AS mom_growth_pct
FROM monthly_revenue;


-- Customer purchase frequency cohort
WITH first_purchase AS (
    SELECT 
        customer_id,
        DATE_TRUNC('month', MIN(order_purchase_timestamp)) AS cohort_month
    FROM fact_orders
    GROUP BY customer_id
),
monthly_activity AS (
    SELECT 
        f.customer_id,
        fp.cohort_month,
        DATE_TRUNC('month', f.order_purchase_timestamp) AS activity_month
    FROM fact_orders f
    JOIN first_purchase fp ON f.customer_id = fp.customer_id
)
SELECT 
    cohort_month,
    COUNT(DISTINCT customer_id) AS cohort_size,
    activity_month,
    COUNT(DISTINCT customer_id) AS active_customers
FROM monthly_activity
GROUP BY cohort_month, activity_month
ORDER BY cohort_month, activity_month;