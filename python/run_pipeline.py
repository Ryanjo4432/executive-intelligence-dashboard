# runs inside docker — preprocess → load → forecast
# skip forecast: docker-compose run --rm pipeline python python/run_pipeline.py --no-forecast
# copy data first (on your machine): python python/copy_data.py

import sys
import time

SKIP_FORECAST = "--no-forecast" in sys.argv


def main():
    print("=" * 55)
    print("  Executive Intelligence Dashboard — Data Pipeline")
    print("=" * 55)

    print("\n[Step 1/3] Preprocessing raw data...\n")
    t0 = time.time()
    try:
        from preprocess import run as preprocess_run
        preprocess_run()
    except FileNotFoundError as e:
        print(f"\nFATAL: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR during preprocessing: {e}")
        raise
    print(f"  Done in {time.time() - t0:.1f}s")

    print("\n[Step 2/3] Loading into PostgreSQL...\n")
    t1 = time.time()
    try:
        from load_to_db import run as load_run
        load_run()
    except Exception as e:
        print(f"\nERROR during DB load: {e}")
        raise
    print(f"  Done in {time.time() - t1:.1f}s")

    if SKIP_FORECAST:
        print("\n[Step 3/3] Forecasting skipped (--no-forecast)")
    else:
        print("\n[Step 3/3] Running revenue forecast...\n")
        t2 = time.time()
        try:
            sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent / "forecasting"))
            from revenue_forecast import run as forecast_run
            forecast_run()
        except Exception as e:
            print(f"\nWARNING: Forecast failed ({e}) — pipeline still succeeded.")
        else:
            print(f"  Done in {time.time() - t2:.1f}s")

    total = time.time() - t0
    print("=" * 55)
    print(f"  Pipeline complete in {total:.1f}s")
    print("  Your data is ready in PostgreSQL.")
    print("=" * 55)


if __name__ == "__main__":
    main()
