-- ============================================================
-- Revenue Intelligence Queries
-- Executive Intelligence Dashboard
-- ============================================================


-- ─── 1. Executive KPI Summary ────────────────────────────────
-- Total revenue, AOV, total orders, avg delivery days

SELECT
    COUNT(DISTINCT order_id)                        AS total_orders,
    ROUND(SUM(revenue)::NUMERIC, 2)                 AS total_revenue,
    ROUND(AVG(total_order_value)::NUMERIC, 2)       AS avg_order_value,
    ROUND(AVG(delivery_days)::NUMERIC, 1)           AS avg_delivery_days,
    ROUND(
        100.0 * SUM(CASE WHEN is_late_delivery THEN 1 ELSE 0 END) / COUNT(*),
        1
    )                                               AS late_delivery_pct
FROM fact_orders
WHERE order_status = 'delivered';


-- ─── 2. Monthly Revenue Trend (with MoM growth %) ────────────
-- Uses window function LAG to compare month over month

WITH monthly AS (
    SELECT
        order_year,
        order_month,
        DATE_TRUNC('month', order_purchase_timestamp) AS month_start,
        ROUND(SUM(revenue)::NUMERIC, 2)               AS monthly_revenue,
        COUNT(DISTINCT order_id)                       AS order_count
    FROM fact_orders
    WHERE order_status = 'delivered'
    GROUP BY order_year, order_month, DATE_TRUNC('month', order_purchase_timestamp)
)
SELECT
    month_start,
    order_year,
    order_month,
    monthly_revenue,
    order_count,
    LAG(monthly_revenue) OVER (ORDER BY month_start)  AS prev_month_revenue,
    ROUND(
        100.0 * (monthly_revenue - LAG(monthly_revenue) OVER (ORDER BY month_start))
              / NULLIF(LAG(monthly_revenue) OVER (ORDER BY month_start), 0),
        1
    )                                                  AS mom_growth_pct,
    SUM(monthly_revenue) OVER (ORDER BY month_start)  AS cumulative_revenue
FROM monthly
ORDER BY month_start;


-- ─── 3. Quarterly Revenue Breakdown ──────────────────────────

SELECT
    order_year,
    order_quarter,
    ROUND(SUM(revenue)::NUMERIC, 2)           AS quarterly_revenue,
    COUNT(DISTINCT order_id)                   AS orders,
    COUNT(DISTINCT customer_unique_id)         AS unique_customers,
    ROUND(AVG(total_order_value)::NUMERIC, 2)  AS avg_order_value
FROM fact_orders
WHERE order_status = 'delivered'
GROUP BY order_year, order_quarter
ORDER BY order_year, order_quarter;


-- ─── 4. Revenue by Product Category (ranked) ─────────────────
-- Shows top and bottom categories with rank window function

WITH category_revenue AS (
    SELECT
        product_category_name_english                        AS category,
        ROUND(SUM(revenue)::NUMERIC, 2)                      AS total_revenue,
        COUNT(DISTINCT order_id)                              AS orders,
        ROUND(AVG(price)::NUMERIC, 2)                        AS avg_price,
        ROUND(SUM(freight_value)::NUMERIC, 2)                AS total_freight,
        ROUND(100.0 * SUM(freight_value) / NULLIF(SUM(revenue), 0), 1) AS freight_pct
    FROM fact_orders
    WHERE order_status = 'delivered'
      AND product_category_name_english IS NOT NULL
    GROUP BY product_category_name_english
)
SELECT
    category,
    total_revenue,
    orders,
    avg_price,
    total_freight,
    freight_pct,
    RANK() OVER (ORDER BY total_revenue DESC)  AS revenue_rank,
    RANK() OVER (ORDER BY orders DESC)         AS order_volume_rank,
    ROUND(100.0 * total_revenue / SUM(total_revenue) OVER (), 2) AS revenue_share_pct
FROM category_revenue
ORDER BY revenue_rank;


-- ─── 5. Revenue by State (regional heat map data) ────────────

SELECT
    customer_state,
    ROUND(SUM(revenue)::NUMERIC, 2)                          AS total_revenue,
    COUNT(DISTINCT order_id)                                  AS orders,
    COUNT(DISTINCT customer_unique_id)                        AS customers,
    ROUND(AVG(total_order_value)::NUMERIC, 2)                AS avg_order_value,
    RANK() OVER (ORDER BY SUM(revenue) DESC)                 AS revenue_rank,
    ROUND(100.0 * SUM(revenue) / SUM(SUM(revenue)) OVER (), 2) AS revenue_share_pct
FROM fact_orders
WHERE order_status = 'delivered'
GROUP BY customer_state
ORDER BY total_revenue DESC;


-- ─── 6. Rolling 30-Day Revenue ───────────────────────────────
-- For smooth trend line in Power BI

WITH daily AS (
    SELECT
        DATE_TRUNC('day', order_purchase_timestamp) AS day,
        ROUND(SUM(revenue)::NUMERIC, 2)              AS daily_revenue
    FROM fact_orders
    WHERE order_status = 'delivered'
    GROUP BY DATE_TRUNC('day', order_purchase_timestamp)
)
SELECT
    day,
    daily_revenue,
    ROUND(
        AVG(daily_revenue) OVER (
            ORDER BY day
            ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
        )::NUMERIC, 2
    ) AS rolling_30d_avg
FROM daily
ORDER BY day;


-- ─── 7. Top 20 Best-Selling Products ─────────────────────────

SELECT
    f.product_id,
    p.product_category_name_english AS category,
    COUNT(DISTINCT f.order_id)       AS times_ordered,
    ROUND(SUM(f.revenue)::NUMERIC, 2) AS total_revenue,
    ROUND(AVG(f.price)::NUMERIC, 2)   AS avg_price,
    ROUND(AVG(r.review_score), 2)     AS avg_review_score
FROM fact_orders f
JOIN products p ON f.product_id = p.product_id
LEFT JOIN order_reviews r ON f.order_id = r.order_id
WHERE f.order_status = 'delivered'
GROUP BY f.product_id, p.product_category_name_english
ORDER BY times_ordered DESC
LIMIT 20;


-- ─── 8. Revenue Leakage — Freight Cost Analysis ───────────────
-- High freight-to-price ratio = potential pricing problem

WITH leakage AS (
    SELECT
        product_category_name_english                               AS category,
        ROUND(SUM(revenue)::NUMERIC, 2)                             AS total_revenue,
        ROUND(SUM(freight_value)::NUMERIC, 2)                       AS total_freight,
        ROUND(100.0 * SUM(freight_value) / NULLIF(SUM(revenue), 0), 1) AS freight_revenue_ratio,
        COUNT(DISTINCT order_id)                                    AS orders
    FROM fact_orders
    WHERE order_status = 'delivered'
      AND product_category_name_english IS NOT NULL
    GROUP BY product_category_name_english
)
SELECT *,
    CASE
        WHEN freight_revenue_ratio > 30 THEN 'High Leakage'
        WHEN freight_revenue_ratio > 15 THEN 'Medium Leakage'
        ELSE 'Healthy'
    END AS leakage_flag
FROM leakage
ORDER BY freight_revenue_ratio DESC;


-- ─── 9. Seller Performance Ranking ───────────────────────────
-- Uses NTILE to bucket sellers into performance tiers

WITH seller_stats AS (
    SELECT
        f.seller_id,
        f.seller_state,
        ROUND(SUM(f.revenue)::NUMERIC, 2)        AS total_revenue,
        COUNT(DISTINCT f.order_id)                AS total_orders,
        ROUND(AVG(r.review_score), 2)             AS avg_review_score,
        ROUND(AVG(f.delivery_days)::NUMERIC, 1)   AS avg_delivery_days
    FROM fact_orders f
    LEFT JOIN order_reviews r ON f.order_id = r.order_id
    WHERE f.order_status = 'delivered'
    GROUP BY f.seller_id, f.seller_state
)
SELECT
    *,
    NTILE(4) OVER (ORDER BY total_revenue DESC) AS revenue_quartile,
    CASE NTILE(4) OVER (ORDER BY total_revenue DESC)
        WHEN 1 THEN 'Top 25%'
        WHEN 2 THEN 'Upper Mid'
        WHEN 3 THEN 'Lower Mid'
        WHEN 4 THEN 'Bottom 25%'
    END AS performance_tier
FROM seller_stats
ORDER BY total_revenue DESC;


-- ─── 10. Payment Method Breakdown ────────────────────────────

SELECT
    primary_payment_type,
    COUNT(DISTINCT order_id)                   AS orders,
    ROUND(SUM(total_payment)::NUMERIC, 2)      AS total_value,
    ROUND(AVG(total_payment)::NUMERIC, 2)      AS avg_order_value,
    ROUND(AVG(payment_installments)::NUMERIC, 1) AS avg_installments,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct_of_orders
FROM order_payments_aggregated
WHERE primary_payment_type NOT IN ('not_defined')
GROUP BY primary_payment_type
ORDER BY orders DESC;
