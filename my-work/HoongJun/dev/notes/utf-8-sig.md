# CSV encoding: why `utf-8-sig` (the BOM gotcha)

**Context:** `p1_el/meltano-raw-csv/meltano.yml` sets `encoding: utf-8-sig` on every `tap-csv` file.

## What a BOM is
A **BOM** (Byte-Order Mark) is an invisible 3-byte prefix — `EF BB BF` — that some tools
(Excel, Windows editors) prepend to UTF-8 files.

## Why it breaks things
The BOM sits at the very start of the file, so it glues onto the **first column's header**.
Read as plain `utf-8`, the first header becomes:

```
"﻿customer_id"   ← invisible BOM stuck to the name, not "customer_id"
```

Consequences (all silent):
- `keys: [customer_id]` no longer matches → **primary key / dedup fails**
- the column lands in BigQuery under a corrupted name → `stg_*` models selecting `customer_id` break / get nulls
- joins on that key break downstream

## The fix
`utf-8-sig` = "utf-8 **with signature**". On read it **consumes and discards the BOM** if present,
and behaves exactly like `utf-8` when there's none. So it's safe to set everywhere — you don't need
to know which files have a BOM.

## How to detect a BOM (don't assume — verify)
First 3 bytes = `ef bb bf` means BOM present:
```bash
head -c 3 file.csv | xxd -p
# efbbbf            -> BOM present (needs utf-8-sig)
# 22... (a quote ") -> no BOM, header starts with "col_name"
```

## Actual finding for the Olist CSVs (2026-06)
Checked all 9 files — **only one** actually had a BOM:

| file | first 3 bytes | BOM? |
|---|---|---|
| product_category_name_translation.csv | `ef bb bf` | ✅ yes |
| the other 8 (orders, customers, …) | `22 ..` (`"`) | no |

So `utf-8-sig` was justified by **one** file — but setting it tap-wide is the right defensive call:
it fixes that file and is harmless for the rest.

## Takeaway
Don't assume file encoding. `head -c 3 file | xxd` tells you per file. When loading CSVs of unknown
origin, default to `utf-8-sig` so a stray BOM can't silently corrupt your first column / keys.
