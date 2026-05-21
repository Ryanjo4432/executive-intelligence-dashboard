import os
import pandas as pd
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import create_engine, text
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

PROCESSED = Path(__file__).parent.parent / "data" / "processed"

PG_USER = os.getenv("POSTGRES_USER", "postgres")
PG_PASS = os.getenv("POSTGRES_PASSWORD", "1234")
PG_HOST = os.getenv("POSTGRES_HOST", "host.docker.internal")
PG_PORT = os.getenv("POSTGRES_PORT", "5432")
PG_DB   = os.getenv("POSTGRES_DB", "executive_db")

DB_URL = f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}"


def log(msg):
    print(f"  [load_to_db] {msg}")


def create_database():
    conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASS, dbname="postgres")
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (PG_DB,))
    if not cur.fetchone():
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(PG_DB)))
        log(f"Created database: {PG_DB}")
    else:
        log(f"Database already exists: {PG_DB}")
    cur.close()
    conn.close()


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS customers (
    customer_id              VARCHAR(50) PRIMARY KEY,
    customer_unique_id       VARCHAR(50),
    customer_zip_code_prefix VARCHAR(10),
    customer_city            VARCHAR(100),
    customer_state           VARCHAR(5)
);

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

CREATE TABLE IF NOT EXISTS geolocation (
    geolocation_zip_code_prefix VARCHAR(10) PRIMARY KEY,
    geolocation_lat             NUMERIC(12,8),
    geolocation_lng             NUMERIC(12,8),
    geolocation_city            VARCHAR(100),
    geolocation_state           VARCHAR(5)
);

-- fact_orders is created by pandas so it picks up all columns automatically

CREATE INDEX IF NOT EXISTS idx_orders_customer     ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_status       ON orders(order_status);
CREATE INDEX IF NOT EXISTS idx_orders_purchase_ts  ON orders(order_purchase_timestamp);
CREATE INDEX IF NOT EXISTS idx_order_items_product ON order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_order_items_seller  ON order_items(seller_id);
"""

FACT_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_fact_purchase_ts ON fact_orders(order_purchase_timestamp);
CREATE INDEX IF NOT EXISTS idx_fact_customer    ON fact_orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_fact_category    ON fact_orders(product_category_name_english);
CREATE INDEX IF NOT EXISTS idx_fact_state       ON fact_orders(customer_state);
"""

# drop everything first so we can reload cleanly without FK conflicts
DROP_SQL = """
DROP TABLE IF EXISTS fact_orders               CASCADE;
DROP TABLE IF EXISTS order_items               CASCADE;
DROP TABLE IF EXISTS order_payments            CASCADE;
DROP TABLE IF EXISTS order_payments_aggregated CASCADE;
DROP TABLE IF EXISTS order_reviews             CASCADE;
DROP TABLE IF EXISTS orders                    CASCADE;
DROP TABLE IF EXISTS customers                 CASCADE;
DROP TABLE IF EXISTS products                  CASCADE;
DROP TABLE IF EXISTS sellers                   CASCADE;
DROP TABLE IF EXISTS geolocation               CASCADE;
DROP TABLE IF EXISTS forecast_daily            CASCADE;
DROP TABLE IF EXISTS forecast_monthly          CASCADE;
"""


def create_schema(engine):
    with engine.connect() as conn:
        conn.execute(text(DROP_SQL))
        conn.execute(text(SCHEMA_SQL))
        conn.commit()
    log("Schema dropped and recreated")


def load_table(engine, filename, table_name, chunksize=5000, if_exists="append"):
    filepath = PROCESSED / filename
    if not filepath.exists():
        log(f"WARNING: {filename} not found, skipping.")
        return
    df = pd.read_csv(filepath, low_memory=False)
    df.to_sql(table_name, engine, if_exists=if_exists, index=False, chunksize=chunksize, method="multi")
    log(f"Loaded {table_name}: {len(df):,} rows")


def run():
    print("\n=== Loading Data into PostgreSQL ===\n")
    print(f"  Target: {PG_HOST}:{PG_PORT}/{PG_DB}")

    create_database()
    engine = create_engine(DB_URL, echo=False)
    create_schema(engine)

    # dimensions first (FK dependencies), then facts
    load_table(engine, "customers.csv",                 "customers")
    load_table(engine, "sellers.csv",                   "sellers")
    load_table(engine, "products.csv",                  "products")
    load_table(engine, "orders.csv",                    "orders")
    load_table(engine, "order_items.csv",               "order_items")
    load_table(engine, "order_payments.csv",            "order_payments")
    load_table(engine, "order_payments_aggregated.csv", "order_payments_aggregated")
    load_table(engine, "order_reviews.csv",             "order_reviews")
    load_table(engine, "geolocation.csv",               "geolocation")
    load_table(engine, "fact_orders.csv",               "fact_orders", if_exists="replace")

    with engine.connect() as conn:
        conn.execute(text(FACT_INDEX_SQL))
        conn.commit()
    log("fact_orders indexes created")

    print("\n=== Data load complete ===\n")
    print(f"  Connect Power BI to: localhost:{PG_PORT}  |  Database: {PG_DB}")
    print(f"  Username: {PG_USER}  |  Password: {PG_PASS}\n")


if __name__ == "__main__":
    run()
