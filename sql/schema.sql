-- ============================================================
-- Executive Intelligence Dashboard — Database Schema
-- Database: executive_db
-- ============================================================

-- Run this manually in pgAdmin or psql if you want to set up
-- the schema without the Python pipeline. The pipeline creates
-- these automatically via load_to_db.py.

-- ─── Dimension Tables ────────────────────────────────────────

CREATE TABLE IF NOT EXISTS customers (
    customer_id              VARCHAR(50) PRIMARY KEY,
    customer_unique_id       VARCHAR(50),
    customer_zip_code_prefix VARCHAR(10),
    customer_city            VARCHAR(100),
    customer_state           VARCHAR(5)
);

CREATE TABLE IF NOT EXISTS sellers (
    seller_id               VARCHAR(50) PRIMARY KEY,
    seller_zip_code_prefix  VARCHAR(10),
    seller_city             VARCHAR(100),
    seller_state            VARCHAR(5)
);

CREATE TABLE IF NOT EXISTS products (
    product_id                    VARCHAR(50) PRIMARY KEY,
    product_category_name         VARCHAR(100),
    product_category_name_english VARCHAR(100),
    product_name_length           INTEGER,
    product_description_length    INTEGER,
    product_photos_qty            INTEGER,
    product_weight_g              NUMERIC,
    product_length_cm             NUMERIC,
    product_height_cm             NUMERIC,
    product_width_cm              NUMERIC
);

CREATE TABLE IF NOT EXISTS geolocation (
    geolocation_zip_code_prefix VARCHAR(10) PRIMARY KEY,
    geolocation_lat             NUMERIC(12,8),
    geolocation_lng             NUMERIC(12,8),
    geolocation_city            VARCHAR(100),
    geolocation_state           VARCHAR(5)
);

-- ─── Fact Tables ──────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS orders (
    order_id                      VARCHAR(50) PRIMARY KEY,
    customer_id                   VARCHAR(50) REFERENCES customers(customer_id),
    order_status                  VARCHAR(30),
    order_purchase_timestamp      TIMESTAMP,
    order_approved_at             TIMESTAMP,
    order_delivered_carrier_date  TIMESTAMP,
    order_delivered_customer_date TIMESTAMP,
    order_estimated_delivery_date TIMESTAMP,
    delivery_days                 INTEGER,
    is_late_delivery              BOOLEAN,
    order_year                    INTEGER,
    order_month                   INTEGER,
    order_quarter                 INTEGER
);

CREATE TABLE IF NOT EXISTS order_items (
    order_id            VARCHAR(50),
    order_item_id       INTEGER,
    product_id          VARCHAR(50) REFERENCES products(product_id),
    seller_id           VARCHAR(50) REFERENCES sellers(seller_id),
    shipping_limit_date TIMESTAMP,
    price               NUMERIC(10,2),
    freight_value       NUMERIC(10,2),
    total_item_revenue  NUMERIC(10,2),
    PRIMARY KEY (order_id, order_item_id)
);

CREATE TABLE IF NOT EXISTS order_payments (
    order_id             VARCHAR(50),
    payment_sequential   INTEGER,
    payment_type         VARCHAR(30),
    payment_installments INTEGER,
    payment_value        NUMERIC(10,2),
    PRIMARY KEY (order_id, payment_sequential)
);

CREATE TABLE IF NOT EXISTS order_payments_aggregated (
    order_id             VARCHAR(50) PRIMARY KEY,
    total_payment        NUMERIC(10,2),
    payment_installments INTEGER,
    primary_payment_type VARCHAR(30)
);

CREATE TABLE IF NOT EXISTS order_reviews (
    review_id               VARCHAR(50) PRIMARY KEY,
    order_id                VARCHAR(50),
    review_score            INTEGER,
    review_comment_title    TEXT,
    review_comment_message  TEXT,
    review_creation_date    TIMESTAMP,
    review_answer_timestamp TIMESTAMP,
    is_positive_review      BOOLEAN,
    is_negative_review      BOOLEAN
);

-- ─── Master Fact (denormalized, optimized for BI) ─────────────

CREATE TABLE IF NOT EXISTS fact_orders (
    order_id                      VARCHAR(50),
    order_item_id                 INTEGER,
    product_id                    VARCHAR(50),
    seller_id                     VARCHAR(50),
    price                         NUMERIC(10,2),
    freight_value                 NUMERIC(10,2),
    total_item_revenue            NUMERIC(10,2),
    customer_id                   VARCHAR(50),
    order_status                  VARCHAR(30),
    order_purchase_timestamp      TIMESTAMP,
    order_approved_at             TIMESTAMP,
    order_delivered_customer_date TIMESTAMP,
    order_estimated_delivery_date TIMESTAMP,
    delivery_days                 INTEGER,
    is_late_delivery              BOOLEAN,
    order_year                    INTEGER,
    order_month                   INTEGER,
    order_quarter                 INTEGER,
    total_payment                 NUMERIC(10,2),
    primary_payment_type          VARCHAR(30),
    customer_unique_id            VARCHAR(50),
    customer_city                 VARCHAR(100),
    customer_state                VARCHAR(5),
    product_category_name_english VARCHAR(100),
    seller_city                   VARCHAR(100),
    seller_state                  VARCHAR(5),
    revenue                       NUMERIC(10,2),
    total_order_value             NUMERIC(10,2),
    PRIMARY KEY (order_id, order_item_id)
);

-- ─── Indexes ──────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_orders_customer     ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_status       ON orders(order_status);
CREATE INDEX IF NOT EXISTS idx_orders_purchase_ts  ON orders(order_purchase_timestamp);
CREATE INDEX IF NOT EXISTS idx_order_items_product ON order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_order_items_seller  ON order_items(seller_id);
CREATE INDEX IF NOT EXISTS idx_fact_purchase_ts    ON fact_orders(order_purchase_timestamp);
CREATE INDEX IF NOT EXISTS idx_fact_customer       ON fact_orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_fact_category       ON fact_orders(product_category_name_english);
CREATE INDEX IF NOT EXISTS idx_fact_state          ON fact_orders(customer_state);
