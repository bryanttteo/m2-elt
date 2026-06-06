# Data issues & recommended handling (Olist raw CSVs → BigQuery)

Findings from loading `datasets/*.csv` into `olist_bronze_dev` and building the dbt
stage/gold layers. Counts are from the actual load (project `sctp-team2-project2-elt`,
location `US`). Each item lists the **issue**, **evidence**, and **how it's handled /
recommended usage**.

---

## 1. UTF-8 BOM on `product_category_name_translation.csv`
- **Issue:** the file begins with a UTF-8 BOM (`EF BB BF`). A naive read leaves the
  BOM glued to the first column name (`﻿product_category_name`).
- **Evidence:** `head -c3 | xxd` → `efbbbf`.
- **Handling:** read every CSV with **`encoding="utf-8-sig"`** (strips the BOM).
  Already applied in `_csv_header()` / `_csv_record_count()` (loader) and `encoding: utf-8-sig`
  in `meltano.yml`. The BigQuery load skips the header row, so the BOM never reaches data.

## 2. All-text file defeats BigQuery header autodetection
- **Issue:** `product_category_name_translation` has **two text columns**. With
  `autodetect=True`, BigQuery can't tell the header row from data (all STRING) and
  names the columns `string_field_0` / `string_field_1`. The Meltano path (which reads
  the header) would instead produce real names → **two load paths disagree**.
- **Evidence:** first manual load produced `string_field_0/1`; this is also why the
  original `sources.yml` referenced `string_field_*`.
- **Handling:** loader `_is_all_text()` detects this (no numeric value in the first data
  row) and supplies an **explicit STRING schema named from the BOM-stripped header**.
  Typed files keep autodetect. Both load paths now yield `product_category_name`,
  `product_category_name_english`.

## 3. Embedded newlines inside quoted fields (`olist_order_reviews_dataset.csv`)
- **Issue:** `review_comment_message` contains line breaks **inside** double-quoted
  values, so a row spans multiple physical lines. BigQuery rejects this by default
  (`Missing close quote character`), and `wc -l` over-counts rows.
- **Evidence:** load failed at line 14 until fixed; `wc -l` ≠ true record count.
- **Handling:** load with **`allow_quoted_newlines=True`** (set in `_load_csv_to_bq`).
  Count rows with a real CSV parser, not `wc -l` (see `_csv_record_count`).

## 4. Duplicate `review_id` in reviews
- **Issue:** `olist_order_reviews_raw` has duplicate review ids.
- **Evidence:** 99,224 rows vs **98,410 distinct `review_id` → 814 duplicate rows**.
- **Handling:** `stg_order_reviews` dedups to one row per `review_id`
  (`QUALIFY ROW_NUMBER() … ORDER BY review_answer_timestamp DESC`).

## 5. Multiple reviews per order
- **Issue:** a single order can have more than one review, so `order_id` is **not**
  unique in reviews.
- **Evidence:** **547 orders have >1 review**.
- **Handling:** `dim_reviews` is keyed by `order_id` and keeps the **latest** review per
  order (dedup by `order_id ORDER BY review_answer_timestamp DESC`). If you need every
  review, join `stg_order_reviews` (keyed by `review_id`) instead of `dim_reviews`.

## 6. Geolocation is one-row-per-point, not one-row-per-zip
- **Issue:** `olist_geolocation_raw` has many lat/lng points per zip prefix. Joining
  it raw to sellers/customers **fans out** the result.
- **Evidence:** **1,000,163 rows but only 19,015 distinct zip prefixes** (~98% are extra
  points per zip).
- **Handling:** `stg_geolocation` collapses to **one row per zip** so downstream joins
  don't explode. ⚠️ Current pick is arbitrary (first row). **Recommended:** pick a
  representative point — e.g. `AVG(lat)`, `AVG(lng)` per zip, or the modal city/state —
  if precise geocoding matters.

## 7. Misspelled product columns (`lenght`)
- **Issue:** source headers misspell "length" as **`lenght`**:
  `product_name_lenght`, `product_description_lenght`.
- **Evidence:** confirmed in the bronze schema.
- **Handling:** kept verbatim through stage/gold to match the source (renaming would
  break `SELECT *` staging). **Recommended:** alias to corrected names in a future
  semantic layer if exposed to BI users.

## 8. Missing / empty timestamps for incomplete orders
- **Issue:** delivery timestamps are empty for orders not yet delivered; empty strings,
  not a sentinel.
- **Evidence:** **2,965 of 99,441 orders have NULL `order_delivered_customer_date`**
  (autodetect typed it TIMESTAMP; empty → NULL). Comparing the column to `''` errors.
- **Handling:** treat as nullable; models `CAST(... AS TIMESTAMP)` and never assume a
  delivery date exists. Don't filter on `= ''` — use `IS NULL`.

## 9. `payment_type` — native `not_defined` plus null-safety
- **Issue:** `payment_type` includes a literal **`not_defined`** value in the raw data
  (alongside boleto/credit_card/debit_card/voucher); nulls are also possible in some
  extracts.
- **Evidence:** distinct = `['boleto','credit_card','debit_card','not_defined','voucher']`;
  null `payment_type` = 0 in this extract.
- **Handling:** `fact_orders` applies `COALESCE(payment_type,'not_defined')` and the
  `accepted_values` test includes `not_defined`.

## 10. Null IDs (defensive, historical)
- **Issue:** earlier extracts had null `order_id` / `customer_id` / `order_item_id` /
  `seller_id` (see commits 1658304, c61bea9).
- **Evidence:** **0 nulls in the current extract**, but filters are retained for safety.
- **Handling:** `fact_orders` filters `WHERE … IS NOT NULL` on the join keys.

## 11. Fact grain is collapsed to one row per order
- **Issue:** `fact_orders` joins orders × order_items × order_payments (which fans out),
  then **dedups to one row per `order_id`** — so only one item/payment survives per order.
- **Evidence:** orders 99,441; order_items 112,650; **`fact_orders` = 98,666 rows**
  (orders without a non-null item/seller are dropped).
- **Handling:** intentional (preserves the original model's behaviour). ⚠️ **Recommended:**
  if you need line-item or payment-level analytics, build a separate
  `fact_order_items` at grain `(order_id, order_item_id)` and a `fact_payments` at
  `(order_id, payment_sequential)` rather than reading `fact_orders`.

## 12. Meltano metadata columns (`_sdc_*`)
- **Issue:** the Meltano `target-bigquery` loader (`denormalized: true`) appends
  `_sdc_*` metadata columns. The manual loader does not.
- **Handling:** staging uses `SELECT *`, so those columns would pass through only on the
  Meltano path. **Recommended:** if you standardise on Meltano, either drop `_sdc_*` in
  staging or set `flattening`/`load_method` to avoid them — keep the two paths' output
  schemas identical.

---

## 13. Pipeline / tooling bugs found & fixed
Not data quality, but bugs hit while building the pipeline — recorded so they don't bite
again (full detail in `CHANGES.md`).

- **macOS `make` 3.81 ignores `.ONESHELL:`** — each recipe line runs in a *separate*
  shell, so `source .env.<ENV>` in one line was gone by the time `dbt build` ran on the
  next. Effect: `make dbt-build ENV=jun` silently built into the **shared `_dev`**
  datasets (masked because the dbt `env_var` defaults equal the dev names).
  **Fix:** write the dbt recipes as a single `; \`-continued shell invocation instead of
  relying on `.ONESHELL`. **Lesson:** on macOS make, never split env-dependent steps
  across recipe lines; verify with `make -n <target>` and check the dataset actually
  written.
- **`dbt_project.yml` model key mismatch** — models were keyed under
  `brazil_ecommerce_proj` (≠ project name `brazil_ecommerce`), silently disabling every
  per-folder setting (materialization, schema, tags). **Fix:** key under the real project
  name.
- **`generate_schema_name`** — without an override, dbt-bigquery builds datasets named
  `<target>_<custom_schema>`. **Fix:** macro returns the custom schema verbatim so
  `+schema` maps straight to `olist_stage_*` / `olist_gold_mart_*`.
- **Dagster `DBT_DIR` path** — pointed at `p3_dbt_project` instead of
  `p3_dbt_project/brazil_ecommerce` (no `dbt_project.yml` one level up). **Fix:** point at
  the project dir.
- **`python-dotenv` not installed by `make install`** — pip's resolver skipped it on the
  first pass. **Fix / lesson:** `pip install python-dotenv` and verify imports
  (`python -c "import dotenv, dagster_dbt, google.cloud.bigquery, dbt.adapters.bigquery"`).

## Quick reference — load settings that matter
| Setting | Why |
|---|---|
| `encoding="utf-8-sig"` | strip BOM (issue 1) |
| `allow_quoted_newlines=True` | multiline review comments (issue 3) |
| explicit STRING schema for all-text files | stable column names (issue 2) |
| dedup in staging (`QUALIFY ROW_NUMBER`) | duplicate review_id / geolocation fan-out (4,5,6) |
| count rows with a CSV parser, not `wc -l` | quoted newlines inflate line counts (issue 3) |
