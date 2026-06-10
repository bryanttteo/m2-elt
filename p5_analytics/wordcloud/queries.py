"""SQL against ``dim_reviews`` in the Olist gold mart.

``dim_reviews`` may be a Type-2 SCD (one row per review *version*) depending on the
deployed build, so we keep only the latest version per ``review_id`` (by answer
timestamp) to count each review once — this works whether or not the SCD columns are
present. Most Olist reviews have no free text, so we surface the comment title and
message as-is and let the app filter to non-empty ones for the text analysis.
"""
from __future__ import annotations

import config

DR = config.table("dim_reviews")

# One row per review (latest version), with both free-text fields, the score, and the
# answer timestamp (used for the time-trend view). Whitespace-only strings are
# normalised to NULL so the app's "has a comment" logic is clean.
REVIEWS_SQL = f"""
SELECT
  review_id,
  review_score,
  NULLIF(TRIM(review_comment_title),   '') AS title,
  NULLIF(TRIM(review_comment_message), '') AS message,
  CAST(review_answer_timestamp AS TIMESTAMP) AS answer_ts,
  DATE(DATE_TRUNC(DATE(review_answer_timestamp), MONTH)) AS answer_month
FROM {DR}
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY review_id ORDER BY review_answer_timestamp DESC
) = 1
"""
