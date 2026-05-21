import pandas as pd
import numpy as np
from pathlib import Path
import warnings

warnings.filterwarnings("ignore")

RAW = Path(__file__).parent.parent / "data" / "raw"
PROCESSED = Path(__file__).parent.parent / "data" / "processed"


def log(msg):
    print(f"  [preprocess] {msg}")


def process_customers():
    df = pd.read_csv(RAW / "olist_customers_dataset.csv")
    df["customer_city"] = df["customer_city"].str.strip().str.title()
    df["customer_state"] = df["customer_state"].str.strip().str.upper()
    df["customer_zip_code_prefix"] = df["customer_zip_code_prefix"].astype(str).str.zfill(5)
    df = df.drop_duplicates(subset="customer_id")
    df.to_csv(PROCESSED / "customers.csv", index=False)
    log(f"customers: {len(df):,} rows")
    return df


def process_orders():
    df = pd.read_csv(RAW / "olist_orders_dataset.csv")

    date_cols = [
        "order_purchase_timestamp", "order_approved_at",
        "order_delivered_carrier_date", "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ]
    for col in date_cols:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    delivered = df["order_delivered_customer_date"].notna()
    estimated = df["order_estimated_delivery_date"].notna()

    df["delivery_days"] = np.where(
        delivered,
        (df["order_delivered_customer_date"] - df["order_purchase_timestamp"]).dt.days,
        np.nan,
    )
    df["is_late_delivery"] = np.where(
        delivered & estimated,
        df["order_delivered_customer_date"] > df["order_estimated_delivery_date"],
        False,
    )
    df["order_year"] = df["order_purchase_timestamp"].dt.year
    df["order_month"] = df["order_purchase_timestamp"].dt.month
    df["order_quarter"] = df["order_purchase_timestamp"].dt.quarter

    df = df.drop_duplicates(subset="order_id")
    df.to_csv(PROCESSED / "orders.csv", index=False)
    log(f"orders: {len(df):,} rows")
    return df


def process_order_items():
    df = pd.read_csv(RAW / "olist_order_items_dataset.csv")
    df["shipping_limit_date"] = pd.to_datetime(df["shipping_limit_date"], errors="coerce")
    df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0)
    df["freight_value"] = pd.to_numeric(df["freight_value"], errors="coerce").fillna(0)
    df["total_item_revenue"] = df["price"] + df["freight_value"]
    df.to_csv(PROCESSED / "order_items.csv", index=False)
    log(f"order_items: {len(df):,} rows")
    return df


def process_order_payments():
    df = pd.read_csv(RAW / "olist_order_payments_dataset.csv")
    df["payment_value"] = pd.to_numeric(df["payment_value"], errors="coerce").fillna(0)
    df["payment_type"] = df["payment_type"].str.strip().str.lower()

    # some orders have multiple payment methods, grab the biggest one as primary
    order_totals = (
        df.groupby("order_id")
        .agg(
            total_payment=("payment_value", "sum"),
            payment_installments=("payment_installments", "max"),
            primary_payment_type=("payment_value", lambda x: df.loc[x.index, "payment_type"].iloc[x.argmax()]),
        )
        .reset_index()
    )

    df.to_csv(PROCESSED / "order_payments.csv", index=False)
    order_totals.to_csv(PROCESSED / "order_payments_aggregated.csv", index=False)
    log(f"order_payments: {len(df):,} rows  |  aggregated: {len(order_totals):,} orders")
    return df, order_totals


def process_order_reviews():
    df = pd.read_csv(RAW / "olist_order_reviews_dataset.csv")
    df["review_creation_date"] = pd.to_datetime(df["review_creation_date"], errors="coerce")
    df["review_answer_timestamp"] = pd.to_datetime(df["review_answer_timestamp"], errors="coerce")
    df["review_comment_title"] = df["review_comment_title"].fillna("")
    df["review_comment_message"] = df["review_comment_message"].fillna("")
    df["review_score"] = pd.to_numeric(df["review_score"], errors="coerce")
    df["is_positive_review"] = df["review_score"] >= 4
    df["is_negative_review"] = df["review_score"] <= 2

    # keep latest review per order, then dedupe review_id for the PK
    df = df.sort_values("review_creation_date", ascending=False)
    df = df.drop_duplicates(subset="order_id")
    df = df.drop_duplicates(subset="review_id")

    df.to_csv(PROCESSED / "order_reviews.csv", index=False)
    log(f"order_reviews: {len(df):,} rows")
    return df


def process_products():
    products = pd.read_csv(RAW / "olist_products_dataset.csv")
    translation = pd.read_csv(RAW / "product_category_name_translation.csv")

    # original dataset has a typo in these column names
    products = products.rename(columns={
        "product_name_lenght": "product_name_length",
        "product_description_lenght": "product_description_length",
    })

    products = products.merge(translation, on="product_category_name", how="left")
    products["product_category_name_english"] = (
        products["product_category_name_english"]
        .fillna(products["product_category_name"])
        .str.replace("_", " ").str.strip().str.title()
    )
    products["product_weight_g"] = pd.to_numeric(products["product_weight_g"], errors="coerce")
    products["product_photos_qty"] = pd.to_numeric(products["product_photos_qty"], errors="coerce").fillna(0)
    products = products.drop_duplicates(subset="product_id")

    products.to_csv(PROCESSED / "products.csv", index=False)
    log(f"products: {len(products):,} rows")
    return products


def process_sellers():
    df = pd.read_csv(RAW / "olist_sellers_dataset.csv")
    df["seller_city"] = df["seller_city"].str.strip().str.title()
    df["seller_state"] = df["seller_state"].str.strip().str.upper()
    df["seller_zip_code_prefix"] = df["seller_zip_code_prefix"].astype(str).str.zfill(5)
    df = df.drop_duplicates(subset="seller_id")
    df.to_csv(PROCESSED / "sellers.csv", index=False)
    log(f"sellers: {len(df):,} rows")
    return df


def process_geolocation():
    df = pd.read_csv(RAW / "olist_geolocation_dataset.csv")
    df["geolocation_city"] = df["geolocation_city"].str.strip().str.title()
    df["geolocation_state"] = df["geolocation_state"].str.strip().str.upper()
    df["geolocation_zip_code_prefix"] = df["geolocation_zip_code_prefix"].astype(str).str.zfill(5)

    # one row per zip code (average the coordinates)
    df = (
        df.groupby("geolocation_zip_code_prefix")
        .agg(
            geolocation_lat=("geolocation_lat", "mean"),
            geolocation_lng=("geolocation_lng", "mean"),
            geolocation_city=("geolocation_city", "first"),
            geolocation_state=("geolocation_state", "first"),
        )
        .reset_index()
    )

    df.to_csv(PROCESSED / "geolocation.csv", index=False)
    log(f"geolocation: {len(df):,} unique zip codes")
    return df


def build_master_fact(orders, order_items, order_payments_agg, customers, products, sellers):
    fact = order_items.merge(orders, on="order_id", how="left")
    fact = fact.merge(order_payments_agg, on="order_id", how="left")
    fact = fact.merge(customers, on="customer_id", how="left")
    fact = fact.merge(products, on="product_id", how="left")
    fact = fact.merge(sellers, on="seller_id", how="left")

    fact["revenue"] = fact["price"]
    fact["total_order_value"] = fact["total_payment"].fillna(fact["total_item_revenue"])

    fact.to_csv(PROCESSED / "fact_orders.csv", index=False)
    log(f"fact_orders (master): {len(fact):,} rows, {len(fact.columns)} columns")
    return fact


def run():
    print("\n=== Preprocessing Olist Dataset ===\n")

    missing = [f for f in [
        "olist_orders_dataset.csv", "olist_order_items_dataset.csv",
        "olist_order_payments_dataset.csv", "olist_order_reviews_dataset.csv",
        "olist_customers_dataset.csv", "olist_products_dataset.csv",
        "olist_sellers_dataset.csv", "olist_geolocation_dataset.csv",
        "product_category_name_translation.csv",
    ] if not (RAW / f).exists()]

    if missing:
        print("ERROR: Missing raw data files:")
        for f in missing:
            print(f"  - {f}")
        print("\nRun: python python/copy_data.py  (on your local machine, not in Docker)")
        raise FileNotFoundError("Raw data files missing. Run copy_data.py first.")

    PROCESSED.mkdir(parents=True, exist_ok=True)

    customers = process_customers()
    orders = process_orders()
    order_items = process_order_items()
    _, order_payments_agg = process_order_payments()
    process_order_reviews()
    products = process_products()
    sellers = process_sellers()
    process_geolocation()
    build_master_fact(orders, order_items, order_payments_agg, customers, products, sellers)

    print("\n=== Preprocessing complete ===\n")


if __name__ == "__main__":
    run()
