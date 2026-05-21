# run this on your machine first before docker, not inside the container
# python python/copy_data.py

import shutil
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SOURCE = Path(
    os.getenv(
        "RAW_DATA_SOURCE",
        r"C:\Users\josel\PhyPrjts\Revenue Leak Detector\data\raw"
    )
)

DEST = Path(__file__).parent.parent / "data" / "raw"

EXPECTED_FILES = [
    "olist_orders_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_customers_dataset.csv",
    "olist_products_dataset.csv",
    "olist_sellers_dataset.csv",
    "olist_geolocation_dataset.csv",
    "product_category_name_translation.csv",
]


def main():
    if not SOURCE.exists():
        print(f"ERROR: Source path not found: {SOURCE}")
        print("Update RAW_DATA_SOURCE in your .env file.")
        return

    DEST.mkdir(parents=True, exist_ok=True)
    copied, skipped = 0, 0

    for filename in EXPECTED_FILES:
        src_file = SOURCE / filename
        dst_file = DEST / filename

        if not src_file.exists():
            print(f"  WARNING: Not found in source: {filename}")
            continue

        if dst_file.exists():
            print(f"  Skipped (already exists): {filename}")
            skipped += 1
            continue

        print(f"  Copying: {filename} ({src_file.stat().st_size / 1_048_576:.1f} MB)")
        shutil.copy2(src_file, dst_file)
        copied += 1

    print(f"\nDone. Copied: {copied}  |  Skipped: {skipped}")
    print(f"Files ready in: {DEST}")


if __name__ == "__main__":
    main()
