# Executive Summary
## Olist E-Commerce — Business Intelligence Analysis

---

## Business Context

Olist is a Brazilian e-commerce marketplace connecting small sellers to major retail platforms. This analysis covers **~100,000 orders** placed between **2016–2018** across all Brazilian states, spanning 32,000+ products and 3,000+ sellers.

The goal: give leadership a clear picture of where the business is healthy, where it's bleeding, and what to do about it.

---

## 1. Revenue Performance

### What's working
- **Total GMV** across the dataset exceeds **R$ 13.5 million**
- **Q4 consistently outperforms** all other quarters — seasonal uplift is real and predictable
- **São Paulo alone generates ~40% of revenue** — the market concentration is both a strength and a risk
- **Health & Beauty, Watches & Gifts, and Computers** are the highest AOV categories

### What needs attention
- Revenue growth is strong in 2017–2018 but **shows early plateauing signs** heading into late 2018
- **Top 3 states (SP, RJ, MG) account for ~60% of orders** — heavy geographic concentration
- **Average Order Value** sits around **R$ 137** — room to grow through bundling and upsell

### Monthly Trend
Revenue follows a clear seasonal curve with peaks in November (Black Friday) and dips in February. Any marketing calendar should be built around this pattern.

---

## 2. Customer Intelligence

### Retention is the core problem
| Metric | Value |
|--------|-------|
| One-time buyers | ~97% |
| Repeat buyers | ~3% |
| Avg orders per customer | 1.03 |

This is the most important number in the entire analysis. Nearly every customer who buys once never comes back. This is not unusual for a marketplace, but it means **acquisition cost is being paid with almost zero LTV recovery.**

### CLV Segmentation
| Tier | Share of Customers | Share of Revenue |
|------|--------------------|-----------------|
| Platinum | 20% | ~45% |
| Gold | 20% | ~20% |
| Silver | 20% | ~15% |
| Bronze | 20% | ~12% |
| Standard | 20% | ~8% |

The Platinum tier is carrying the business. Losing one Platinum customer requires acquiring roughly 6 Standard customers to replace the revenue.

### RFM Segments — Action Priority
| Segment | Priority | Action |
|---------|----------|--------|
| Champions | Protect | Loyalty program, early access |
| At Risk High Value | URGENT | Win-back campaign, personal outreach |
| Loyal Customers | Grow | Cross-sell into adjacent categories |
| Lost | Low | Re-engagement email only, low spend |
| New Customers | Nurture | Onboarding sequence, second-purchase incentive |

---

## 3. Revenue Leakage

### Freight cost is silently killing margins

Categories where freight exceeds 30% of product revenue:

| Category | Freight/Revenue Ratio | Flag |
|----------|-----------------------|------|
| Office Furniture | ~35–40% | Critical |
| Large Appliances | ~32–38% | Critical |
| Construction Tools | ~28–33% | High |
| Garden Tools | ~25–30% | High |

These categories look profitable on gross revenue but may be margin-negative once logistics costs are fully loaded.

**Recommendation:** Run a full unit economics analysis on the top 5 leakage categories before running any promotions on them.

### Late deliveries compound the problem
- Late deliveries correlate directly with 1 and 2 star reviews
- 1–2 star reviews correlate with zero repeat purchase
- The path: late delivery → bad review → permanent churn

States with the highest late delivery rates tend to be outside the Southeast corridor — logistics infrastructure is thinner there.

---

## 4. Sales Intelligence

### Category winners (by order volume + revenue)
1. **Health & Beauty** — highest frequency, strong AOV, good review scores
2. **Watches & Gifts** — premium AOV, seasonal spike in Q4
3. **Bed/Bath/Table** — consistent volume year-round
4. **Sports & Leisure** — growing trend heading into 2018
5. **Computers & Accessories** — high AOV, tech-savvy customer base

### Category concerns
- **Office Furniture:** high revenue, high freight, high return signals
- **Telephony:** high volume but declining AOV trend
- **Fashion (shoes/clothing):** high negative review rate — sizing/fit returns

### Seasonal patterns
| Month | Pattern |
|-------|---------|
| Jan–Feb | Post-holiday dip — lowest order volumes |
| May–Jun | Mid-year recovery |
| Aug–Sep | Pre-holiday buildup |
| Nov | Peak — Black Friday effect clearly visible |
| Dec | Second peak — gift season |

---

## 5. Revenue Forecast

The Prophet model was trained on ~2 years of daily revenue data with multiplicative weekly and yearly seasonality.

**Key forecast outputs:**
- **Next 30 days:** Projected to follow the established seasonal trend
- **Confidence interval:** ±15% — uncertainty grows beyond 60 days
- **Model fit:** Strong on seasonal patterns, weaker on sudden demand shocks

The forecast tables (`forecast_daily`, `forecast_monthly`) are live in PostgreSQL and update every time the pipeline runs.

---

## 6. Strategic Recommendations

### Priority 1 — Fix retention before scaling acquisition
Every R$1 spent on acquiring new customers into a 97% churn funnel is largely wasted. Before increasing CAC, invest in:
- Post-purchase email sequence (Day 3, Day 14, Day 30 after delivery)
- Second-purchase incentive for first-time buyers
- Target the "At Risk High Value" RFM segment specifically

**Expected impact:** Moving retention from 3% to 6% doubles the revenue contribution from the existing customer base.

### Priority 2 — Address freight leakage in top 5 categories
Run a unit economics audit on Office Furniture, Large Appliances, and Construction Tools. Options:
- Negotiate bulk shipping contracts for heavy goods
- Add minimum order value thresholds for free shipping
- Reprice affected SKUs to absorb logistics cost

**Expected impact:** 5–8% gross margin improvement on affected categories.

### Priority 3 — Expand seller supply in Southeast Brazil
SP, RJ, MG have proven demand but seller density could support higher order volumes. More local sellers = faster delivery = better reviews = higher repeat rate.

**Expected impact:** Delivery time reduction in key markets, direct correlation with review score improvement.

### Priority 4 — Invest in Champions and Loyal Customers retention
These two segments generate the majority of revenue. A loyalty program, even a simple one, gives them a reason to stay on Olist instead of going direct to competing platforms.

**Expected impact:** 10–15% CLV increase in top segments over 12 months.

### Priority 5 — Fix product quality signals in low-review categories
Categories averaging below 3.0 stars have a structural problem — product quality, listing accuracy, or fulfillment. Scaling marketing into them accelerates churn. Fix the product first.

**Expected impact:** Review score improvement from 2.8 → 3.5 in a category typically reduces return rate by 20–30%.

---

## Conclusion

The data tells a consistent story: **Olist has strong acquisition and weak retention.** The geographic and category concentration means the business is also more fragile than the top-line numbers suggest.

The highest-leverage moves are in retention, freight optimization, and protecting the top customer segments — not in chasing new acquisition volume.

The infrastructure to measure all of this is now in place. The next step is acting on it.

---

*Analysis based on Olist Brazilian E-Commerce dataset (2016–2018)*
*Built with PostgreSQL · Python · Prophet · Power BI*
