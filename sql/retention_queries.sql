-- ============================================================
-- Customer Retention & Intelligence Queries
-- Executive Intelligence Dashboard
-- ============================================================


-- ─── 1. Customer Retention Rate ──────────────────────────────
-- How many customers placed more than one order

WITH order_counts AS (
    SELECT
        customer_unique_id,
        COUNT(DISTINCT order_id) AS total_orders
    FROM fact_orders
    WHERE order_status = 'delivered'
    GROUP BY customer_unique_id
)
SELECT
    COUNT(*)                                                AS total_customers,
    SUM(CASE WHEN total_orders > 1 THEN 1 ELSE 0 END)      AS repeat_customers,
    SUM(CASE WHEN total_orders = 1 THEN 1 ELSE 0 END)      AS one_time_customers,
    ROUND(
        100.0 * SUM(CASE WHEN total_orders > 1 THEN 1 ELSE 0 END) / COUNT(*),
        2
    )                                                       AS retention_rate_pct,
    ROUND(AVG(total_orders), 2)                             AS avg_orders_per_customer
FROM order_counts;


-- ─── 2. Customer Lifetime Value (CLV) ────────────────────────
-- Total revenue per unique customer, with order frequency and recency

WITH customer_orders AS (
    SELECT
        customer_unique_id,
        COUNT(DISTINCT order_id)                                  AS order_count,
        ROUND(SUM(revenue)::NUMERIC, 2)                           AS lifetime_revenue,
        ROUND(AVG(total_order_value)::NUMERIC, 2)                 AS avg_order_value,
        MIN(order_purchase_timestamp)                             AS first_order,
        MAX(order_purchase_timestamp)                             AS last_order,
        EXTRACT(DAY FROM MAX(order_purchase_timestamp)
            - MIN(order_purchase_timestamp))                      AS customer_lifespan_days
    FROM fact_orders
    WHERE order_status = 'delivered'
    GROUP BY customer_unique_id
)
SELECT
    customer_unique_id,
    order_count,
    lifetime_revenue,
    avg_order_value,
    first_order,
    last_order,
    customer_lifespan_days,
    NTILE(5) OVER (ORDER BY lifetime_revenue DESC) AS clv_quintile,
    CASE NTILE(5) OVER (ORDER BY lifetime_revenue DESC)
        WHEN 1 THEN 'Platinum'
        WHEN 2 THEN 'Gold'
        WHEN 3 THEN 'Silver'
        WHEN 4 THEN 'Bronze'
        WHEN 5 THEN 'Standard'
    END AS customer_tier
FROM customer_orders
ORDER BY lifetime_revenue DESC;


-- ─── 3. CLV Summary by Tier ───────────────────────────────────
-- Aggregate view for Power BI KPI cards

WITH clv_base AS (
    SELECT
        customer_unique_id,
        ROUND(SUM(revenue)::NUMERIC, 2)  AS lifetime_revenue,
        COUNT(DISTINCT order_id)          AS order_count
    FROM fact_orders
    WHERE order_status = 'delivered'
    GROUP BY customer_unique_id
),
tiered AS (
    SELECT *,
        NTILE(5) OVER (ORDER BY lifetime_revenue DESC) AS quintile
    FROM clv_base
)
SELECT
    CASE quintile
        WHEN 1 THEN 'Platinum'
        WHEN 2 THEN 'Gold'
        WHEN 3 THEN 'Silver'
        WHEN 4 THEN 'Bronze'
        WHEN 5 THEN 'Standard'
    END                                                AS customer_tier,
    COUNT(*)                                           AS customers,
    ROUND(SUM(lifetime_revenue)::NUMERIC, 2)           AS total_revenue,
    ROUND(AVG(lifetime_revenue)::NUMERIC, 2)           AS avg_clv,
    ROUND(AVG(order_count), 2)                         AS avg_orders,
    ROUND(100.0 * SUM(lifetime_revenue)
        / SUM(SUM(lifetime_revenue)) OVER (), 1)       AS revenue_share_pct
FROM tiered
GROUP BY quintile
ORDER BY quintile;


-- ─── 4. Monthly Cohort Retention ─────────────────────────────
-- Tracks what % of each monthly cohort is still buying N months later

WITH first_orders AS (
    SELECT
        customer_unique_id,
        DATE_TRUNC('month', MIN(order_purchase_timestamp)) AS cohort_month
    FROM fact_orders
    WHERE order_status = 'delivered'
    GROUP BY customer_unique_id
),
customer_activity AS (
    SELECT
        f.customer_unique_id,
        DATE_TRUNC('month', f.order_purchase_timestamp) AS activity_month,
        fo.cohort_month
    FROM fact_orders f
    JOIN first_orders fo ON f.customer_unique_id = fo.customer_unique_id
    WHERE f.order_status = 'delivered'
),
cohort_size AS (
    SELECT cohort_month, COUNT(DISTINCT customer_unique_id) AS cohort_customers
    FROM first_orders
    GROUP BY cohort_month
)
SELECT
    ca.cohort_month,
    cs.cohort_customers,
    ca.activity_month,
    EXTRACT(MONTH FROM AGE(ca.activity_month, ca.cohort_month)) AS months_since_first_order,
    COUNT(DISTINCT ca.customer_unique_id)                       AS active_customers,
    ROUND(
        100.0 * COUNT(DISTINCT ca.customer_unique_id) / cs.cohort_customers,
        1
    )                                                           AS retention_pct
FROM customer_activity ca
JOIN cohort_size cs ON ca.cohort_month = cs.cohort_month
GROUP BY ca.cohort_month, cs.cohort_customers, ca.activity_month
ORDER BY ca.cohort_month, ca.activity_month;


-- ─── 5. Churn Risk Indicators ────────────────────────────────
-- Customers who bought once and never came back, by recency

WITH last_purchase AS (
    SELECT
        customer_unique_id,
        COUNT(DISTINCT order_id)                               AS total_orders,
        MAX(order_purchase_timestamp)                          AS last_order_date,
        ROUND(SUM(revenue)::NUMERIC, 2)                        AS total_spent,
        ROUND(AVG(NULLIF(review_score, 0))::NUMERIC, 2)        AS avg_review_score
    FROM fact_orders f
    LEFT JOIN order_reviews r USING (order_id)
    WHERE f.order_status = 'delivered'
    GROUP BY customer_unique_id
)
SELECT
    customer_unique_id,
    total_orders,
    last_order_date,
    total_spent,
    avg_review_score,
    DATE_PART('day', NOW() - last_order_date)  AS days_since_last_order,
    CASE
        WHEN total_orders = 1
             AND DATE_PART('day', NOW() - last_order_date) > 180 THEN 'Churned'
        WHEN total_orders = 1
             AND DATE_PART('day', NOW() - last_order_date) > 90  THEN 'At Risk'
        WHEN total_orders > 1
             AND DATE_PART('day', NOW() - last_order_date) > 180 THEN 'Lapsing'
        ELSE 'Active'
    END AS churn_status
FROM last_purchase
ORDER BY days_since_last_order DESC;


-- ─── 6. Churn Summary for KPI Card ───────────────────────────

WITH last_purchase AS (
    SELECT
        customer_unique_id,
        COUNT(DISTINCT order_id) AS total_orders,
        MAX(order_purchase_timestamp) AS last_order_date
    FROM fact_orders
    WHERE order_status = 'delivered'
    GROUP BY customer_unique_id
),
classified AS (
    SELECT *,
        CASE
            WHEN total_orders = 1 AND DATE_PART('day', NOW() - last_order_date) > 180 THEN 'Churned'
            WHEN total_orders = 1 AND DATE_PART('day', NOW() - last_order_date) > 90  THEN 'At Risk'
            WHEN total_orders > 1 AND DATE_PART('day', NOW() - last_order_date) > 180 THEN 'Lapsing'
            ELSE 'Active'
        END AS churn_status
    FROM last_purchase
)
SELECT
    churn_status,
    COUNT(*) AS customers,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
FROM classified
GROUP BY churn_status
ORDER BY customers DESC;


-- ─── 7. Repeat Purchase Rate by Category ─────────────────────
-- Which categories drive customers back

WITH customer_categories AS (
    SELECT
        customer_unique_id,
        product_category_name_english AS category,
        COUNT(DISTINCT order_id)       AS purchases_in_category
    FROM fact_orders
    WHERE order_status = 'delivered'
      AND product_category_name_english IS NOT NULL
    GROUP BY customer_unique_id, product_category_name_english
)
SELECT
    category,
    COUNT(DISTINCT customer_unique_id)                           AS total_buyers,
    SUM(CASE WHEN purchases_in_category > 1 THEN 1 ELSE 0 END)  AS repeat_buyers,
    ROUND(
        100.0 * SUM(CASE WHEN purchases_in_category > 1 THEN 1 ELSE 0 END)
              / COUNT(DISTINCT customer_unique_id),
        1
    )                                                            AS repeat_rate_pct
FROM customer_categories
GROUP BY category
HAVING COUNT(DISTINCT customer_unique_id) > 50
ORDER BY repeat_rate_pct DESC;


-- ─── 8. High-Value Customer Segments (RFM) ───────────────────
-- Recency, Frequency, Monetary segmentation

WITH rfm_raw AS (
    SELECT
        customer_unique_id,
        DATE_PART('day', NOW() - MAX(order_purchase_timestamp))  AS recency_days,
        COUNT(DISTINCT order_id)                                  AS frequency,
        ROUND(SUM(revenue)::NUMERIC, 2)                          AS monetary
    FROM fact_orders
    WHERE order_status = 'delivered'
    GROUP BY customer_unique_id
),
rfm_scored AS (
    SELECT *,
        NTILE(5) OVER (ORDER BY recency_days ASC)  AS r_score,
        NTILE(5) OVER (ORDER BY frequency DESC)    AS f_score,
        NTILE(5) OVER (ORDER BY monetary DESC)     AS m_score
    FROM rfm_raw
)
SELECT
    customer_unique_id,
    recency_days,
    frequency,
    monetary,
    r_score,
    f_score,
    m_score,
    (r_score + f_score + m_score)          AS rfm_total,
    CASE
        WHEN (r_score + f_score + m_score) >= 13 THEN 'Champions'
        WHEN (r_score + f_score + m_score) >= 10 THEN 'Loyal Customers'
        WHEN r_score >= 4 AND f_score <= 2   THEN 'New Customers'
        WHEN r_score <= 2 AND m_score >= 4   THEN 'At Risk High Value'
        WHEN r_score <= 2                    THEN 'Lost'
        ELSE 'Potential'
    END AS rfm_segment
FROM rfm_scored
ORDER BY rfm_total DESC;


-- ─── 9. RFM Segment Summary ───────────────────────────────────

WITH rfm_raw AS (
    SELECT
        customer_unique_id,
        DATE_PART('day', NOW() - MAX(order_purchase_timestamp)) AS recency_days,
        COUNT(DISTINCT order_id) AS frequency,
        ROUND(SUM(revenue)::NUMERIC, 2) AS monetary
    FROM fact_orders WHERE order_status = 'delivered'
    GROUP BY customer_unique_id
),
rfm_scored AS (
    SELECT *,
        NTILE(5) OVER (ORDER BY recency_days ASC) AS r_score,
        NTILE(5) OVER (ORDER BY frequency DESC)   AS f_score,
        NTILE(5) OVER (ORDER BY monetary DESC)    AS m_score
    FROM rfm_raw
),
rfm_segmented AS (
    SELECT *,
        CASE
            WHEN (r_score + f_score + m_score) >= 13 THEN 'Champions'
            WHEN (r_score + f_score + m_score) >= 10 THEN 'Loyal Customers'
            WHEN r_score >= 4 AND f_score <= 2        THEN 'New Customers'
            WHEN r_score <= 2 AND m_score >= 4        THEN 'At Risk High Value'
            WHEN r_score <= 2                         THEN 'Lost'
            ELSE 'Potential'
        END AS rfm_segment
    FROM rfm_scored
)
SELECT
    rfm_segment,
    COUNT(*)                                    AS customers,
    ROUND(AVG(monetary)::NUMERIC, 2)            AS avg_clv,
    ROUND(AVG(frequency), 2)                    AS avg_orders,
    ROUND(AVG(recency_days))                    AS avg_recency_days,
    ROUND(SUM(monetary)::NUMERIC, 2)            AS total_revenue,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct_of_customers
FROM rfm_segmented
GROUP BY rfm_segment
ORDER BY total_revenue DESC;


-- ─── 10. Review Score vs Revenue Correlation ──────────────────
-- Do higher-rated categories earn more?

SELECT
    f.product_category_name_english          AS category,
    ROUND(AVG(r.review_score), 2)            AS avg_review_score,
    ROUND(SUM(f.revenue)::NUMERIC, 2)        AS total_revenue,
    COUNT(DISTINCT f.order_id)               AS orders,
    SUM(CASE WHEN r.is_negative_review THEN 1 ELSE 0 END) AS negative_reviews,
    ROUND(
        100.0 * SUM(CASE WHEN r.is_negative_review THEN 1 ELSE 0 END)
              / NULLIF(COUNT(r.review_id), 0),
        1
    )                                        AS negative_review_pct
FROM fact_orders f
LEFT JOIN order_reviews r ON f.order_id = r.order_id
WHERE f.order_status = 'delivered'
  AND f.product_category_name_english IS NOT NULL
GROUP BY f.product_category_name_english
HAVING COUNT(DISTINCT f.order_id) > 100
ORDER BY avg_review_score DESC;
