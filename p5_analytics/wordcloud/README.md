# Olist Reviews — Text Analysis (Streamlit)

Word cloud and NLP-light analysis over the free-text fields of `dim_reviews`
(`review_comment_title`, `review_comment_message`) in the Olist gold mart
(`olist_gold_mart_prod`). Reviews are Brazilian **Portuguese** — see `text.py` for the
extended (PT + EN) stopword handling.

## What it shows
- KPIs: review count, % with a comment / title, average score.
- **Word cloud** over the chosen field (title / message / both), filtered by score.
- Top 20 words and bigrams.
- Comment-length distribution and average length by review score.
- Side-by-side **low-score (1–2★) vs high-score (4–5★)** word clouds.
- A sample of raw comments.

## Run locally
```bash
make venv
ENV=prod make run          # http://localhost:8502
```
Always queries BigQuery live; needs ADC or `GOOGLE_APPLICATION_CREDENTIALS`
(resolved from the repo-root `.env.<ENV>`, same as the sibling apps). Query results are
cached in-session for 1h via `st.cache_data`.

## Deploy (Cloud Run)
```bash
make deploy                # Cloud Build image + deploy, live BigQuery via the service account
```

## Files
| File | Purpose |
|---|---|
| `app.py` | Streamlit UI |
| `config.py` | BigQuery project/dataset/credential resolution |
| `bq.py` | Cached live BigQuery query helper |
| `queries.py` | `dim_reviews` SQL (current versions only) |
| `text.py` | Tokenizing, PT+EN stopwords, n-grams |
