# EDA Plan & Results — Olist Brazilian E-commerce (Gold Mart)

> Companion planning doc for `eda.ipynb`, as required by `readme-eda.md`.
> **Section A** is the *plan* (written before implementation).
> **Section B** is the *results* (filled in after running the notebook).

---

## Section A — Plan (before implementation)

### A.0 Data reconnaissance (what's actually in the warehouse)

| Asset | Location | Notes |
| --- | --- | --- |
| `fact_orders` | `sctp-team2-project2-elt.olist_gold_mart_prod` | Order-**item** grain. 113,425 rows / 99,441 distinct orders. DQ flag columns included. |
| `dim_customers` | same dataset | `customer_unique_id` links repeat purchases across `customer_id`s. |
| `dim_products` | same dataset | English `product_category`. |
| `dim_sellers` | same dataset | seller + geolocation. |
| `dim_reviews` | same dataset | **Deployed version is stale — has no `order_id`.** Cannot join to orders. |
| `reviews_dbt_scd_snapshot` | `sctp-team2-project2-elt.snapshots` | **Has `order_id` + SCD validity.** Source of truth for the review↔order link. |
| Date span | — | 2016-09-04 → 2018-10-17. |

**Decision (confirmed with stakeholder):** source reviews from
`snapshots.reviews_dbt_scd_snapshot` (current rows: `dbt_valid_to IS NULL`),
since prod gold `dim_reviews` lacks `order_id`. Slightly bends the "gold only"
rule but is the only way to quantify the central narrative until the reworked
`dim_reviews` model is deployed.

**Auth (confirmed):** service-account keyfile preferred. All current
`sctp-team2-project2-elt` keys are **rotated/invalid** (`Invalid JWT
Signature`). Notebook therefore tries the keyfile first and **falls back to
gcloud ADC** (`hoongjundsai@gmail.com`, verified working) so it runs today and
picks up the keyfile automatically once a fresh one is minted.

### A.1 The business question (refined problem statement)

Three executives each see one face of the same elephant:
- **CEO** — GMV grows but marketing spend climbs to sustain it; margins soft.
- **CMO** — re-engagement underperforms; blames a "non-sticky brand."
- **CTO** — delivery complaints + low reviews treated as operational noise.

**Hypothesis the EDA tests:** *the binding constraint on profitable growth is the
repeat-purchase rate, and the largest controllable lever on repeat purchase is
delivery experience. Late delivery → low review scores → customers don't return.
The cause lives in logistics (CTO), surfaces as a retention/marketing problem
(CMO), and bleeds margin (CEO).* If true, fixing delivery is cheaper than buying
growth with marketing.

### A.2 EDA steps planned (each = purpose → method → expected read)

1. **Setup & connect** — teach BQ client + `query → DataFrame`.
2. **Data overview** — grain, `shape`, `info`, `describe`, missingness. Purpose: trust the data before analysing.
3. **Data quality** — order-status mix + DQ flags. Purpose: know what to exclude (e.g. non-delivered) and quantify noise.
4. **GMV trend** — monthly revenue line. Purpose: confirm/quantify the CEO's "growth."
5. **Retention** — repeat-purchase rate via `customer_unique_id`. Purpose: test whether retention is the constraint.
6. **Product categories** — top categories by GMV (Pareto). Purpose: where revenue concentrates.
7. **Delivery performance** — lead-time distribution, on-time rate, late rate by state. Purpose: size the logistics problem.
8. **Reviews + the linkage** — score distribution, then **avg review by on-time vs late**. Purpose: the smoking gun.
9. **Causal chain** — does a poor first experience (late / low score) reduce the chance of a 2nd order? Purpose: connect logistics → retention.
10. **RFM segmentation** — Recency/Frequency/Monetary segments. Purpose: who to protect, who to win back (deliverable in M5 README).
11. **Conclusions & recommendations** — mapped to CEO/CMO/CTO.
12. **Q1–Q4 written answers** — per `readme-eda.md`.

### A.3 Key visualisations planned
Monthly GMV line · repeat-rate KPI + new-vs-returning bar · top-category horizontal
bar · delivery lead-time histogram · on-time rate by state bar · review-score
distribution · **review-score-by-delivery grouped bar (headline)** · repeat-rate
by first-order experience bar · RFM segment treemap/bar.

### A.4 Assumptions & scope
- **GMV = Σ `price`** at item grain (product revenue; freight reported separately).
- Delivery analysis restricted to `order_status = 'delivered'` with non-null dates.
- "Late" = `order_delivered_customer_date > order_estimated_delivery_date`.
- One **current** review per order (`MAX(review_score)` if duplicates).
- **Scoped out:** seller-level economics, geospatial mapping, payment-installment
  margin modelling, NPS reconstruction — noted as next steps, not built now.

---

## Section B — Results (after implementation)

> ✅ **Reconciled with the executed `eda.ipynb`** (Restart & Run All, service-account
> keyfile auth, 16/16 code cells, 0 errors, 10 charts). All numbers below are the
> notebook's actual outputs, not estimates.

### B.0 Run facts
- Data pulled: **99,441 orders** (from 113,425 order-items), span **2016-09-04 → 2018-10-17**.
- Missingness (meaningful, not errors): `delivered_ts` 3.0% (undelivered orders),
  `review_score` 1.3% (no review), `order_gmv`/`order_freight` 0.8% (orders with no items).

### B.1 Headline findings
- **Retention is the constraint.** 96,096 unique customers placed 99,441 orders →
  only **2,997 customers (3.1%) ever reordered**; **3.4% of all orders are repeats**.
  Growth is almost entirely *new-customer acquisition* — exactly the "working harder
  to grow / rising marketing spend" the CEO feels.
- **GMV is real but acquisition-funded.** Monthly GMV grew **~610%** from Jan-2017 to
  Aug-2018, then plateaued — built on first-time buyers, not loyalty.
- **Delivery is mostly good but the tail is toxic.** Median delivery **10 days**;
  **8.1%** of the 96,470 delivered orders arrive after the promised date, concentrated
  in specific states (a targetable lane problem, not random).
- **Reviews skew positive overall** — average **4.09★**, but **14.6%** are 1–2★.
- **The smoking gun (delivery → satisfaction):**
  | Delivery | n | Avg review | % 1–2★ (detractors) | % 4–5★ (promoters) |
  | --- | --- | --- | --- | --- |
  | On-time | 87,708 | **4.30** | 9.2% | 82.9% |
  | Late | 7,615 | **2.57** | 54.0% | 34.7% |

  A late delivery roughly **halves** the review score (−1.7★) and turns the majority
  of those customers into detractors.
- **The loop closes (experience → repeat).** Customers whose *first* order arrived
  on-time reorder at **3.13%** vs **2.56%** for a late first order — low everywhere
  (Olist is structurally one-shot) but the direction is unambiguous, and repeat rate
  rises monotonically with first-order review score.
- **RFM segments** (mean recency/freq/monetary): the base is dominated by one-and-done
  buyers; the actionable groups are **At-risk high-value** (recency ≈446 days, monetary
  ≈R$280 — protect) and **New / promising** (recency ≈141 days — convert via a good
  first delivery).

### B.2 Interpretation (the elephant, assembled)
Late delivery is *not* operational noise — it is the mechanism converting a paying
customer into a detractor, and detractors don't return. The CMO's "non-sticky
brand" and the CEO's "soft margins / rising spend" are **downstream symptoms** of a
logistics problem the CTO already owns. Spending more on loyalty comms treats the
symptom; tightening delivery reliability treats the cause and is cheaper than
buying replacement growth.

### B.3 Recommendations by stakeholder
- **CTO:** treat on-time delivery as a revenue KPI; target the worst states/lanes
  (largest late-rate × volume). Each prevented late delivery protects ~1.7 review
  points and a retention-eligible customer.
- **CMO:** redirect re-engagement budget toward customers whose *first* experience
  was good (they're winnable); stop spending against a churn cause marketing can't fix.
- **CEO:** the cheapest growth lever is repeat rate via delivery reliability, not
  incremental acquisition spend. A few points of repeat rate compounds GMV without
  rising CAC.

### B.4 Q1–Q4 (full answers in the notebook's final section)
- **Q1 Clarifying questions** — unit economics/CAC? margin by category? promised-date
  source? definition of "repeat" window? (each reframes the priority).
- **Q2 Refined problem** — quantify how much of the retention gap is explained by
  delivery experience, and size the GMV upside of fixing it.
- **Q3 Key decisions** — (1) source reviews from snapshot vs deploy model; (2) GMV at
  item grain on `price`; (3) restrict delivery analysis to delivered orders.
- **Q4 Next week** — model P(repeat | first-order late/score) controlling for
  category & geography; build seller/lane scorecard; quantify R$ at risk.
