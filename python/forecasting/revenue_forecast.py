import os
import warnings
import pandas as pd
import numpy as np
from pathlib import Path
from sqlalchemy import create_engine, text

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent / ".env")
except ImportError:
    pass

warnings.filterwarnings("ignore")

PG_USER = os.getenv("POSTGRES_USER", "postgres")
PG_PASS = os.getenv("POSTGRES_PASSWORD", "1234")
PG_HOST = os.getenv("POSTGRES_HOST", "host.docker.internal")
PG_PORT = os.getenv("POSTGRES_PORT", "5432")
PG_DB   = os.getenv("POSTGRES_DB", "executive_db")

DB_URL = f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}"

FORECAST_DAYS = 90
VISUALS_DIR = Path(__file__).parent.parent.parent / "visuals"


def log(msg):
    print(f"  [forecast] {msg}")


def load_daily_revenue(engine) -> pd.DataFrame:
    # cast needed because fact_orders is created dynamically by pandas (text columns)
    query = """
        SELECT
            DATE_TRUNC('day', order_purchase_timestamp::TIMESTAMP)::DATE AS ds,
            SUM(revenue::NUMERIC) AS y
        FROM fact_orders
        WHERE order_status = 'delivered'
          AND order_purchase_timestamp IS NOT NULL
        GROUP BY DATE_TRUNC('day', order_purchase_timestamp::TIMESTAMP)::DATE
        ORDER BY ds
    """
    df = pd.read_sql(query, engine)
    df["ds"] = pd.to_datetime(df["ds"])
    df["y"] = pd.to_numeric(df["y"], errors="coerce").fillna(0)
    log(f"Loaded {len(df)} days of revenue data ({df['ds'].min().date()} → {df['ds'].max().date()})")
    return df


def linear_trend_forecast(df: pd.DataFrame, periods: int) -> pd.DataFrame:
    df = df.copy()
    df["t"] = (df["ds"] - df["ds"].min()).dt.days
    coeffs = np.polyfit(df["t"], df["y"], 1)
    slope, intercept = coeffs

    last_t = df["t"].max()
    future_dates = pd.date_range(start=df["ds"].max() + pd.Timedelta(days=1), periods=periods, freq="D")
    future_t = last_t + np.arange(1, periods + 1)
    yhat = slope * future_t + intercept

    forecast = pd.DataFrame({
        "ds": future_dates,
        "yhat": np.maximum(yhat, 0),
        "yhat_lower": np.maximum(yhat * 0.85, 0),
        "yhat_upper": np.maximum(yhat * 1.15, 0),
        "model": "linear_trend",
    })

    historical = df.copy()
    historical["yhat"] = slope * df["t"] + intercept
    historical["yhat_lower"] = historical["yhat"] * 0.85
    historical["yhat_upper"] = historical["yhat"] * 1.15
    historical["model"] = "linear_trend"

    return pd.concat([historical[["ds", "yhat", "yhat_lower", "yhat_upper", "model"]], forecast], ignore_index=True)


def holtwinters_forecast(df: pd.DataFrame, periods: int) -> pd.DataFrame:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    # aggregate to monthly — daily data is too noisy for convergence
    monthly = df.copy()
    monthly["month"] = monthly["ds"].dt.to_period("M")
    monthly_agg = monthly.groupby("month")["y"].sum().reset_index()
    monthly_agg["ds"] = monthly_agg["month"].dt.to_timestamp()
    monthly_agg = monthly_agg.iloc[:-1] if len(monthly_agg) > 2 else monthly_agg

    series = monthly_agg.set_index("ds")["y"]

    if len(series) >= 24:
        model = ExponentialSmoothing(series, trend="add", seasonal="add", seasonal_periods=12, damped_trend=True).fit(optimized=True)
    else:
        model = ExponentialSmoothing(series, trend="add", damped_trend=True).fit(optimized=True)

    forecast_months = (periods // 30) + 2
    fitted = model.fittedvalues
    forecast_vals = model.forecast(forecast_months)
    resid_std = float(np.std(model.resid))

    all_rows = []
    for month_ts, yhat_m in forecast_vals.items():
        days = pd.date_range(start=month_ts, periods=pd.Period(month_ts, "M").days_in_month, freq="D")
        daily_val = max(yhat_m / len(days), 0)
        daily_lo  = max((yhat_m - 1.96 * resid_std) / len(days), 0)
        daily_hi  = max((yhat_m + 1.96 * resid_std) / len(days), 0)
        for d in days:
            all_rows.append({"ds": d, "yhat": daily_val, "yhat_lower": daily_lo, "yhat_upper": daily_hi, "model": "holt_winters"})
        if len(all_rows) >= periods:
            break
    future = pd.DataFrame(all_rows[:periods])

    month_fitted = {ts: v for ts, v in fitted.items()}
    hist_rows = []
    for _, row in df.iterrows():
        m = row["ds"].to_period("M").to_timestamp()
        dim = pd.Period(m, "M").days_in_month
        base = month_fitted.get(m, row["y"])
        daily = max(base / dim, 0)
        hist_rows.append({"ds": row["ds"], "yhat": daily, "yhat_lower": max(daily - resid_std / dim, 0), "yhat_upper": daily + resid_std / dim, "model": "holt_winters"})
    historical = pd.DataFrame(hist_rows)

    return pd.concat([historical, future], ignore_index=True)


def prophet_forecast(df: pd.DataFrame, periods: int) -> pd.DataFrame:
    from prophet import Prophet
    model = Prophet(yearly_seasonality=True, weekly_seasonality=True, daily_seasonality=False, seasonality_mode="multiplicative", changepoint_prior_scale=0.05)
    model.fit(df[["ds", "y"]])
    future = model.make_future_dataframe(periods=periods, freq="D")
    forecast = model.predict(future)
    forecast["model"] = "prophet"
    return forecast[["ds", "yhat", "yhat_lower", "yhat_upper", "model"]]


def monthly_rollup(daily_forecast: pd.DataFrame) -> pd.DataFrame:
    df = daily_forecast.copy()
    df["month"] = df["ds"].dt.to_period("M")
    monthly = df.groupby("month").agg(
        forecast_revenue=("yhat", "sum"),
        forecast_lower=("yhat_lower", "sum"),
        forecast_upper=("yhat_upper", "sum"),
    ).reset_index()
    monthly["month"] = monthly["month"].dt.to_timestamp()
    monthly[["forecast_revenue", "forecast_lower", "forecast_upper"]] = monthly[["forecast_revenue", "forecast_lower", "forecast_upper"]].round(2)
    return monthly


def save_forecast_chart(actual: pd.DataFrame, forecast: pd.DataFrame):
    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates

        VISUALS_DIR.mkdir(exist_ok=True)
        fig, ax = plt.subplots(figsize=(14, 6))

        ax.plot(actual["ds"], actual["y"], color="#2563EB", linewidth=1.5, label="Actual Revenue", zorder=3)

        future_mask = forecast["ds"] > actual["ds"].max()
        ax.plot(forecast.loc[future_mask, "ds"], forecast.loc[future_mask, "yhat"],
                color="#F59E0B", linewidth=2, linestyle="--", label="Forecast", zorder=3)
        ax.fill_between(forecast.loc[future_mask, "ds"],
                        forecast.loc[future_mask, "yhat_lower"],
                        forecast.loc[future_mask, "yhat_upper"],
                        alpha=0.2, color="#F59E0B", label="Confidence Interval")

        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        plt.xticks(rotation=45)
        ax.set_title("Revenue Forecast — Next 90 Days", fontsize=14, fontweight="bold")
        ax.set_xlabel("Date")
        ax.set_ylabel("Revenue (BRL)")
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()

        out = VISUALS_DIR / "revenue_forecast.png"
        plt.savefig(out, dpi=150, bbox_inches="tight")
        plt.close()
        log(f"Chart saved → {out}")
    except Exception as e:
        log(f"Chart generation skipped: {e}")


CREATE_FORECAST_TABLES = """
CREATE TABLE IF NOT EXISTS forecast_daily (
    ds          DATE PRIMARY KEY,
    yhat        NUMERIC(12,2),
    yhat_lower  NUMERIC(12,2),
    yhat_upper  NUMERIC(12,2),
    model       VARCHAR(30),
    is_forecast BOOLEAN
);

CREATE TABLE IF NOT EXISTS forecast_monthly (
    month            DATE PRIMARY KEY,
    forecast_revenue NUMERIC(12,2),
    forecast_lower   NUMERIC(12,2),
    forecast_upper   NUMERIC(12,2)
);
"""


def write_forecast_to_db(engine, actual: pd.DataFrame, daily_forecast: pd.DataFrame, monthly: pd.DataFrame):
    with engine.connect() as conn:
        conn.execute(text(CREATE_FORECAST_TABLES))
        conn.commit()

    cutoff = actual["ds"].max()
    daily_out = daily_forecast[["ds", "yhat", "yhat_lower", "yhat_upper", "model"]].copy()
    daily_out["is_forecast"] = daily_out["ds"] > cutoff
    daily_out[["yhat", "yhat_lower", "yhat_upper"]] = daily_out[["yhat", "yhat_lower", "yhat_upper"]].round(2)

    daily_out.to_sql("forecast_daily", engine, if_exists="replace", index=False, method="multi", chunksize=500)
    log(f"Wrote forecast_daily: {len(daily_out)} rows")
    monthly.to_sql("forecast_monthly", engine, if_exists="replace", index=False, method="multi")
    log(f"Wrote forecast_monthly: {len(monthly)} rows")


def print_summary(actual: pd.DataFrame, monthly: pd.DataFrame):
    last_revenue = actual.groupby(actual["ds"].dt.to_period("M"))["y"].sum().iloc[-1]
    future_months = monthly[monthly["month"] > actual["ds"].max()]
    if future_months.empty:
        return

    next_month = future_months.iloc[0]
    growth = 100 * (next_month["forecast_revenue"] - last_revenue) / last_revenue if last_revenue else 0
    arrow = "▲" if growth >= 0 else "▼"

    print("\n" + "─" * 45)
    print("  FORECAST SUMMARY")
    print("─" * 45)
    print(f"  Last full month revenue :  R$ {last_revenue:>12,.2f}")
    print(f"  Next month forecast     :  R$ {next_month['forecast_revenue']:>12,.2f}")
    print(f"  Confidence range        :  R$ {next_month['forecast_lower']:,.0f} – R$ {next_month['forecast_upper']:,.0f}")
    print(f"  Projected MoM growth    :  {arrow} {abs(growth):.1f}%")
    print("─" * 45 + "\n")


def run():
    print("\n=== Revenue Forecasting ===\n")

    engine = create_engine(DB_URL, echo=False)
    actual = load_daily_revenue(engine)

    if len(actual) < 30:
        log("not enough data (need 30+ days)")
        return

    # try Prophet first, then Holt-Winters, then basic linear trend
    try:
        from prophet import Prophet
        Prophet(yearly_seasonality=False)
        log("Using Prophet model")
        daily_forecast = prophet_forecast(actual, FORECAST_DAYS)
    except Exception:
        try:
            log("Prophet unavailable — using Holt-Winters (statsmodels)")
            daily_forecast = holtwinters_forecast(actual, FORECAST_DAYS)
        except Exception as e2:
            log(f"Holt-Winters failed ({e2}) — using linear trend fallback")
            daily_forecast = linear_trend_forecast(actual, FORECAST_DAYS)

    monthly = monthly_rollup(daily_forecast)
    save_forecast_chart(actual, daily_forecast)
    write_forecast_to_db(engine, actual, daily_forecast, monthly)
    print_summary(actual, monthly)

    print("=== Forecasting complete ===\n")


if __name__ == "__main__":
    run()
