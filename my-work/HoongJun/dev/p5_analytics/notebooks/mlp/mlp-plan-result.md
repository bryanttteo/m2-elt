# MLP Plan & Results — Olist Brazilian E-commerce (Gold Mart)

> Companion planning doc for `mlp.ipynb`, mirroring `eda/eda-plan-result.md`.
> **Section A** is the *plan* (written before implementation, driven by the EDA conclusions).
> **Section B** is the *results* (filled in after the pipeline runs end-to-end).
> Requirements this plan satisfies live in `readme-mlp.md`.

---

## Section A — Plan (before implementation)

### A.0 Why this task (carrying the EDA forward, not re-deriving it)

The EDA established a causal chain and quantified it (see `eda/eda-plan-result.md` §B.1):

> **Late delivery → low review → no repeat purchase.**
> On-time orders: avg review **4.30**, repeat **3.13%**. Late orders: avg review **2.57**, repeat **2.56%**.
> A late delivery roughly halves the review score (−1.7★) and turns the majority into detractors.

The single most *controllable* link in that chain — the one that happens **before**
the customer reviews or churns — is **whether an order will be delivered late**. If we
can predict late delivery at (or shortly after) order time, the CTO can intervene on the
toxic 8.1% tail *before* it becomes a 1–2★ review and a lost customer.

**Primary learning task (chosen):**
**Binary classification — predict P(late delivery) for an order**, where
`late = order_delivered_customer_date > order_estimated_delivery_date`.
- Actionable: a late-risk score per order routes to expedited handling / proactive comms.
- Leak-free: all features are knowable at order time (no post-delivery info).
- Directly monetizable via the EDA elasticities (each prevented late delivery ≈ +1.7★ and a retention-eligible customer).

**Secondary task (stretch, same pipeline, config-switchable):**
**Predict P(repeat purchase)** for a customer's first order — the ultimate business
KPI. Kept secondary because the EDA showed repeat is structurally rare (~3%), so it is a
hard, highly-imbalanced target; late-delivery is the higher-signal, higher-leverage win.

> **Design note:** `TARGET` is a config key. The pipeline is built once; switching
> between `late_delivery` and `repeat_purchase` is a config change, not a code change
> (per `readme-mlp.md` Configurability).

### A.1 Data ingestion

- Source: `sctp-team2-project2-elt.olist_gold_mart_prod` via BigQuery client (same
  auth pattern as the EDA: service-account keyfile first, **fallback to gcloud ADC**).
- Grain: aggregate `fact_orders` (order-item) up to **one row per `order_id`** for the
  late-delivery task (the unit a logistics team acts on).
- Restrict to `order_status = 'delivered'` with non-null delivery dates (the only rows
  where the label is defined), exactly as the EDA delivery analysis did.
- Ingestion isolated behind a single `load_data(config)` function so the source is swappable.

### A.2 Label definition (no leakage)

| Task | Positive class | Defined from |
| --- | --- | --- |
| `late_delivery` | delivered after estimate | `delivered_customer_date > estimated_delivery_date` |
| `repeat_purchase` | customer placed a 2nd+ order | `customer_unique_id` order count > 1 |

Class balance is known from the EDA: late ≈ **8.1%** positive → **imbalanced**, which
dictates metric choice (§A.6) and resampling/`class_weight` handling.

### A.3 Feature plan (what's knowable at order time)

| Feature | Source | Processing | Rationale (EDA link) |
| --- | --- | --- | --- |
| `customer_state` | dim_customers | one-hot / target encode | EDA: late rate is **state-concentrated**, a lane problem |
| `seller_state` | dim_sellers | one-hot / target encode | cross-state shipments drive distance/lead-time |
| `same_state` (derived) | cust vs seller | boolean | proxy for shipping distance |
| `product_category` | dim_products | target encode (high-cardinality) | category mix relates to handling/freight |
| `freight_value` | fact_orders | scale (StandardScaler) | freight correlates with distance/weight |
| `price` / `order_gmv` | fact_orders | scale | basket size / handling |
| `product_weight_g`, dims (`length/height/width`) | dim_products | impute median + scale | bulky items ship slower |
| `n_items` (derived) | fact_orders | scale | multi-item orders are harder to fulfil on time |
| `estimated_lead_days` (derived) | estimated − purchase ts | scale | the promise itself encodes route difficulty |
| `purchase_month` / `dow` / `hour` | order_purchase_ts | cyclical encode | seasonality / weekend dispatch effects |
| **Excluded (leakage):** actual delivery/carrier dates, `review_score` | — | dropped | unknown at order time |

Feature engineering encapsulated in a `build_features(df, config)` function /
`ColumnTransformer` so it lifts cleanly into a script and is reused at inference.

### A.4 Preprocessing pipeline (sklearn `Pipeline` + `ColumnTransformer`)

1. Impute (median for numeric, most-frequent / "missing" for categorical).
2. Encode (one-hot for low-card, target/ordinal for high-card categoricals).
3. Scale numeric (StandardScaler).
4. Wrap as a single fitted `Pipeline` so train/inference are identical (no skew).

### A.5 Models (config-switchable, justified on data characteristics)

| Model | Why it fits this data |
| --- | --- |
| **Logistic Regression** (baseline) | interpretable coefficients → tells CTO *which* lanes/features drive risk; fast; honest baseline |
| **Random Forest** | handles non-linear state×category interactions, mixed feature types, robust to scaling |
| **Gradient Boosting (XGBoost/LightGBM)** | usually best on tabular; native `scale_pos_weight` for imbalance; feature importance |

Selected via `MODEL` config key. Hyperparameters tuned with
`RandomizedSearchCV` (search space + `n_iter` configurable), CV stratified on the label.
Imbalance handled with `class_weight`/`scale_pos_weight` (and optional SMOTE as a config flag).

### A.6 Evaluation (metrics chosen for an imbalanced, cost-asymmetric problem)

- **Primary: PR-AUC / Average Precision** — with ~8% positives, ROC-AUC is optimistic;
  precision–recall reflects the minority (late) class we actually care about.
- **Recall on the late class** — missing a late order = a lost customer (high cost), so
  recall is the business-critical lever.
- **Precision @ chosen threshold** — intervention has a cost; we tune the threshold to a
  precision the ops team can absorb.
- **F1 / confusion matrix** — operating-point summary.
- **Calibration** — scores must be probabilities to prioritize interventions.
- ROC-AUC reported as a secondary, comparable-to-literature number only.

Threshold is **tuned to the business cost ratio**, not left at 0.5, and exposed as config.

### A.7 Pipeline architecture (single-responsibility stages → `run.sh`)

```
config (yaml/env/CLI)
        │
   load_data ──▶ make_labels ──▶ build_features ──▶ split (stratified)
        │                                               │
        └────────────────────────────────▶ train (Pipeline+search)
                                                        │
                                                  evaluate ──▶ persist (model.pkl, metrics.json, plots)
```

- Notebook (`mlp.ipynb`) = thin cells calling these functions, runs top-to-bottom.
- Logic lives in importable functions/classes → lifted into `src/*.py`.
- `run.sh` executes the pipeline non-interactively; `requirements.txt` installed separately.
- Config file drives target, model, hyperparameter search, threshold, encodings.

### A.8 Deployment considerations (to note in the notebook)

- **Retraining/refresh:** delivery patterns drift seasonally → scheduled retrain on
  rolling window; the BQ ingestion layer makes this a cron, not a rewrite.
- **Monitoring/drift:** track input drift (state/category mix, freight) and label drift
  (late rate vs the 8.1% baseline); alert on PR-AUC decay.
- **Latency:** scoring is at order-creation time → low-latency single-row inference; the
  fitted `Pipeline` guarantees train/serve parity.
- **Input validation:** reject/flag rows with out-of-range freight/weights, unknown states.
- **Reproducibility:** fixed seeds, pinned `requirements.txt`, versioned config + model artifact.

### A.9 Assumptions & scope

- Late label only defined on delivered orders (in-flight/cancelled excluded from training).
- Geography/category proxies stand in for true distance/carrier data (not in gold mart).
- Scoped out for now: carrier-level features, geospatial routing, cost-optimal
  intervention policy (downstream of the risk score), causal uplift modelling.

---

## Section B — Results (after implementation)

> ✅ Reconciled with the executed `mlp.ipynb` (nbconvert Run-All, 13/13 code cells, 0
> errors) **and** a headless `./run.sh`. BigQuery auth succeeded on the service-account
> keyfile. Numbers below are the pipeline's actual test-set outputs.

### B.0 Run facts
- Ingested **99,441 orders** from the gold mart; cached to `artifacts/orders.parquet`.
- Primary target `late_delivery`: **96,470 rows, 7,826 positive (8.1%)** — matches the EDA
  late rate exactly. Stratified split: **train 77,176 / test 19,294**, seed 42.
- Secondary target `repeat_purchase`: **96,096 rows, 2,997 positive (3.1%)** — also matches
  the EDA. Runs through the same pipeline via `--set target=repeat_purchase`.

### B.1 Model comparison (late_delivery, threshold tuned to recall ≥ 0.70)
| Model | PR-AUC | ROC-AUC | Recall (late) | Precision (late) | F1 |
| --- | --- | --- | --- | --- | --- |
| **hist_gbm** (chosen) | **0.290** | **0.788** | 0.700 | 0.192 | 0.301 |
| logistic_regression | 0.185 | 0.706 | 0.700 | 0.133 | — |

Baseline rate is 8.1%, so hist_gbm's PR-AUC is a **~3.6× lift** over random; it clearly
beats the linear baseline on every metric. (xgboost is wired in and config-selectable but
not installed in this env.)

### B.2 Chosen model & operating point
- **HistGradientBoosting**, tuned threshold ≈ **0.48** → catches **70% of late orders**
  at **19% precision**. Confusion matrix on the 19,294-row test set:
  `[[13117, 4612], [469, 1096]]` (TN, FP / FN, TP).
- Business read: to intervene on a real late order we accept ~4 false alarms — acceptable
  when a missed late delivery costs ~1.7★ and a retention-eligible customer (EDA
  elasticities). The threshold is a config knob (`threshold.min_recall`) the ops team can
  re-tune to its intervention budget.

### B.3 Feature importance / interpretation
- Top drivers align with the EDA as predicted: the **promised lead time
  (`estimated_lead_days`)**, **freight (`order_freight` / `freight_ratio`)**, **order
  bulk (`total_weight_g`, `max_volume_cm3`)**, and **geography (`customer_state` /
  `seller_state` one-hots)** — i.e. the same state/lane and distance/bulk signals the EDA
  flagged as the targetable late-delivery tail.

### B.4 Limitations
- Precision is inherently low at high recall on an 8%-positive problem — expected, and why
  the threshold is exposed rather than fixed at 0.5.
- `repeat_purchase` is hard (PR-AUC ≈ 0.05 over a 3.1% base, ROC-AUC ≈ 0.62): the order-time
  features carry weak signal for it, consistent with the EDA's "structurally one-shot"
  finding. Late-delivery is the higher-leverage win, as planned.
- Geography/category proxy for true distance/carrier data (not in the gold mart).

### B.5 Deployment readiness
- **Ready:** single fitted `Pipeline` (train/serve parity), config-driven model/target/
  threshold, swappable BQ ingestion, persisted `model.pkl` + `metrics.json`, headless
  `run.sh`, pinned `requirements.txt`.
- **Stubbed / next:** scheduled retraining job, drift monitors (input mix + late-rate vs
  8.1% baseline), input validation service, model registry/versioning.
