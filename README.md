# Executive Intelligence Dashboard
### Sales · Retention · Revenue Forecasting

> A decision-support system built for leadership — not a chart collection.
> Answers the questions executives actually ask.

---

## What This Solves

Leadership teams make growth decisions on fragmented data. This system centralizes everything into one intelligence layer:

| Question | Where it's answered |
|----------|-------------------|
| Where are we making money? | Sales Intelligence page |
| Where are we losing customers? | Customer Intelligence + Churn analysis |
| Which regions/products should we scale? | Regional heat maps + Category rankings |
| What will next month's revenue be? | Forecasting page (Prophet model) |

---

## Project Structure

```
executive-intelligence-dashboard/
│
├── data/
│   ├── raw/                          # Olist CSVs (gitignored — run copy_data.py)
│   └── processed/                    # Cleaned, transformed output
│
├── sql/
│   ├── schema.sql                    # Full database schema + indexes
│   ├── revenue_queries.sql           # 10 revenue intelligence queries
│   └── retention_queries.sql         # 10 retention + RFM queries
│
├── python/
│   ├── copy_data.py                  # Copies raw CSVs from source (run on host)
│   ├── preprocess.py                 # Cleans all 9 Olist tables
│   ├── load_to_db.py                 # Creates DB schema + loads into PostgreSQL
│   ├── run_pipeline.py               # Master runner (preprocess → load → forecast)
│   └── forecasting/
│       └── revenue_forecast.py       # Prophet revenue forecast + DB export
│
├── powerbi/
│   └── powerbi_instructions.md       # Full PBI guide: DAX, relationships, pages
│
├── visuals/                          # Generated chart exports
├── insights_report/
│   └── executive_summary.md          # Key findings + strategic recommendations
│
├── docker/
│   └── Dockerfile
│
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

---

## Tech Stack

| Layer | Tool | Why |
|-------|------|-----|
| Database | PostgreSQL (local) | Power BI connects directly, no overhead |
| Pipeline | Python 3.11 in Docker | Reproducible, no local dependency hell |
| SQL | CTEs + Window Functions + JOINs | Shows real analytical SQL skill |
| Forecasting | Facebook Prophet | Handles seasonality automatically |
| Dashboard | Power BI Desktop | Industry-standard executive reporting |

---

## How to Run It

### Prerequisites
- Docker Desktop (running)
- PostgreSQL installed locally on port `5432`
- Power BI Desktop
- Npgsql driver for Power BI → PostgreSQL connection

### Step 1 — Configure environment
```bash
cp .env.example .env
# values are already correct, no edits needed
```

### Step 2 — Copy raw data to project (run on your machine)
```bash
python python/copy_data.py
```

### Step 3 — Run the full pipeline (inside Docker)
```bash
docker-compose run --rm pipeline
```

This single command:
1. Cleans and transforms all 9 Olist CSV files
2. Creates `executive_db` in your local PostgreSQL
3. Loads 10 tables including the `fact_orders` master join
4. Runs revenue forecasting and writes results to `forecast_daily` + `forecast_monthly`

**Expected runtime:** 3–8 minutes depending on machine

### Step 4 — Open Jupyter (optional, for forecasting notebook)
```bash
docker-compose up jupyter
# open http://localhost:8888
```

### Step 5 — Connect Power BI
```
Server:   localhost
Database: executive_db
User:     postgres
Password: 1234
```
Full dashboard build guide → `powerbi/powerbi_instructions.md`

---

## Database

**Database:** `executive_db` on `localhost:5432`

| Table | Rows (approx) | Description |
|-------|--------------|-------------|
| `fact_orders` | ~112K | Master join — use this for most queries |
| `orders` | ~99K | Order lifecycle + delivery dates |
| `order_items` | ~112K | Product line items per order |
| `order_payments` | ~103K | Raw payment rows |
| `order_payments_aggregated` | ~99K | One row per order, total + payment type |
| `order_reviews` | ~99K | Review scores + comments |
| `customers` | ~99K | Customer city/state |
| `products` | ~33K | Product catalog + English categories |
| `sellers` | ~3K | Seller city/state |
| `geolocation` | ~19K | Zip code → lat/lng (deduplicated) |
| `forecast_daily` | ~800 | Daily revenue actual + 90-day forecast |
| `forecast_monthly` | ~30 | Monthly forecast with confidence range |

---

## SQL Intelligence Layer

All queries in `sql/` demonstrate production-level SQL patterns:

**Revenue queries (`revenue_queries.sql`)**
- Executive KPI summary
- Monthly trend with MoM growth % using `LAG()`
- Category revenue with `RANK()` and revenue share %
- Regional heat map data by state
- Rolling 30-day revenue with `AVG() OVER (ROWS BETWEEN...)`
- Seller performance tiers using `NTILE(4)`
- Revenue leakage via freight-to-revenue ratio

**Retention queries (`retention_queries.sql`)**
- Customer retention rate
- Customer Lifetime Value with `NTILE(5)` tiers (Platinum → Standard)
- Monthly cohort retention matrix
- Churn risk classification (Churned / At Risk / Lapsing / Active)
- Full RFM segmentation (Recency · Frequency · Monetary)
- Repeat purchase rate by category
- Review score vs revenue correlation

---

## Dashboard (Power BI)

5 report pages — full build guide in `powerbi/powerbi_instructions.md`

| Page | Key Visuals |
|------|-------------|
| Executive Overview | 6 KPI cards, revenue trend, state map, quarterly bars |
| Sales Intelligence | Category rankings, seasonal trends, payment split |
| Customer Intelligence | Retention rate, churn map, review distribution |
| Revenue Leakage | Freight ratio by category, negative review heatmap |
| Forecasting | Actual vs forecast line, confidence band, monthly table |

**15 DAX measures** included — Revenue, Orders, AOV, Retention Rate, MoM/YoY Growth, Freight Ratio, CLV tiers, Forecast bounds.

---

## Forecasting Model

Uses **Facebook Prophet** with multiplicative seasonality — designed for retail time series with weekly and yearly patterns.

- Trained on 2+ years of daily Olist revenue
- 90-day forward forecast with confidence intervals
- Falls back to linear trend if Prophet is unavailable
- Results written to PostgreSQL for live Power BI consumption
- Chart exported to `visuals/revenue_forecast.png`

---

## Key Business Insights

See `insights_report/executive_summary.md` for full analysis.

**Revenue**
- São Paulo, Rio de Janeiro, and Minas Gerais generate ~60% of total revenue
- Health & Beauty and Watches & Gifts have the highest average order values
- Q4 shows consistent seasonal uplift across all years

**Customers**
- ~97% of customers are one-time buyers — retention is the biggest growth lever
- Top 20% of customers (Platinum + Gold CLV tiers) generate ~65% of revenue
- Customers who leave a positive review (4–5 stars) have 2x higher reorder rate

**Leakage**
- Office furniture and large appliances have freight costs exceeding 30% of revenue
- Late delivery rate correlates strongly with 1–2 star reviews
- High installment orders (6+) show elevated payment failure risk

---

## Strategic Recommendations

**1. Attack the retention problem first**
97% one-time buyer rate means every retained customer is pure upside. A post-purchase email sequence targeting 30-day and 60-day windows costs almost nothing and could double LTV for the top segments.

**2. Cut freight leakage in high-ratio categories**
Office furniture and large home goods are shipping away the margin. Either negotiate bulk rates, add a minimum order threshold, or reprice freight-heavy SKUs.

**3. Double down on Southeast Brazil**
SP + RJ + MG have the highest revenue density AND the shortest delivery times. More seller recruitment here = faster delivery = better reviews = more repeat purchases.

**4. Use the RFM segments for targeted campaigns**
"At Risk High Value" customers are the most urgent — they spent a lot but haven't come back. A win-back campaign targeting this segment specifically beats spray-and-pray discounting.

**5. Fix the low-review categories before scaling them**
Categories with average review scores below 3.0 have structural product or logistics problems. Scaling ad spend into them just amplifies the churn.

---

## Dataset

**Olist Brazilian E-Commerce Public Dataset**
~100,000 orders from 2016–2018 across Brazil
9 CSV files covering the full order lifecycle

Source: [Kaggle — Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
