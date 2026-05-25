# Bronze — Raw Landing Tier  (medallion: BRONZE)
**Produced by:** Module 1 (EL — dlt / Meltano) · **Owner:** John / Bryan

### BigQuery Dataset
| BigQuery Dataset | Dataset ID  | URL |
| ---| --- | --- |
| sctp-team2-project2elt | olin_bronze | https://console.cloud.google.com/bigquery?ws=!1m4!1m3!3m2!1ssctp-team2-project2-elt!2solin_bronze |

### Extract and Load Summary 
| | CSV line count | Filename |	Loaded in BQ | Rows loaded in BQ | BQ dataset (schema name) | BQ tablename | Remarks |
| --- | ---- |
|1|	99442 |	olist_customers_dataset.csv | OK | 99,441 | olin_bronze | olist_customers_dataset | |
|2| 1000164 | olist_geolocation_dataset.csv | OK | 1,000,163 | olin_bronze | olist_geolocation_dataset | |		
|3| 112651 | olist_order_items_dataset.csv | OK | 112,650 | olin_bronze | olist_order_items_dataset | |		
|4| 103887 | olist_order_payments_dataset.csv | OK | 103,886 | olin_bronze | olist_order_payments_dataset | |		
|5|	104720 | olist_order_reviews_dataset.csv | OK |	99,224 | olin_bronze | olist_order_reviews_dataset | some "review_comment_message" have \n which causes the line count to over-count as anew record. |
|6|	99442 | olist_orders_dataset.csv | OK | 99,441 | olin_bronze | olist_orders_dataset | |	
|7|	32952 | olist_products_dataset.csv | OK | 32,951 | olin_bronze | olist_products_dataset | |
|8|	3096 | olist_sellers_dataset.csv | OK | 3,095 | olin_bronze | olist_sellers_dataset | |	
|9|	71 | product_category_name_translation.csv | OK | 71 | olin_bronze | product_category_name_translation | Using manual definition of schema. Skipped header 1 row. Per BQ docu header rows where all fields are strings may not have the header detected |

### Raw data files in Google Cloud Storage
| Project ID | Bucket Name | URL |
| --- | --- | --- |
| sctp-team2-project2-elt | m2_olin_raw | https://console.cloud.google.com/storage/browser/m2_olin_raw?project=sctp-team2-project2-elt | 


## Purpose
Bronze is the **raw landing tier** of the medallion architecture: source data loaded 1:1, untransformed, as the immutable foundation everything else builds on. This folder documents the tier and holds bronze-level contracts/notes — the **data itself lives in BigQuery** (`raw_commerce`), produced by the EL tools in `../EL/`.

> Why a folder if the data is in BigQuery? For symmetry with `silver/`-via-dbt and `gold/`-via-dbt, and to give the bronze *contract* (table names, expected columns, load conventions) a documented home that M3 reads against.

## Needs (inputs)
- The 9 Olist CSVs landed by `../EL/dlt/` or `../p1_el/meltano/`.

## Produces (outputs / what bronze guarantees)
- BigQuery dataset **`raw_commerce`** with 9 tables, types inferred, load-tracked:
  `orders, order_items, customers, products, payments, reviews, sellers, geolocation, category_translation`.
- A stable **bronze contract**: table + key-column names that downstream silver models depend on.

## Hand-off to next (→ M3 silver)
dbt's `models/silver/_sources.yml` registers these `raw_commerce` tables as dbt **sources**. Silver models read from here via `{{ source('raw_commerce', '<table>') }}` — never from the CSVs directly.

## Contract notes (keep updated)
- Bronze is **append/replace only** — no business logic, no cleaning. Cleaning happens in silver.
- Document any known raw-data quirks here (e.g., `reviews` has null timestamps; `products` has null categories; `geolocation` has duplicate zip prefixes) so silver and M4 know what to handle.

## Files
- `bronze_contract.md` — (to author) the authoritative list of bronze tables + columns + known quirks.
