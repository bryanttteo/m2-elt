"""Olist Reviews — Text Analysis (Streamlit + wordcloud + matplotlib).

Word cloud and NLP-light analysis over the free-text fields of ``dim_reviews``
(``review_comment_title`` and ``review_comment_message``) in the Olist gold mart.
Reviews are Brazilian Portuguese; see text.py for the stopword handling.

Run locally:  ENV=prod streamlit run app.py
Serve (prod): streamlit run app.py --server.port $PORT --server.address 0.0.0.0
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from wordcloud import WordCloud

import bq
import queries
import text as T

st.set_page_config(page_title="Olist · Review Text Analysis", page_icon="💬",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown(
    """
    <style>
      .block-container { padding-top: 2rem; max-width: 1400px; }
      [data-testid="stMetricValue"] { font-size: 1.7rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------- data ----
@st.cache_data(ttl=3600)
def load_reviews() -> pd.DataFrame:
    return bq.run(queries.REVIEWS_SQL)


df = load_reviews()

# ---------------------------------------------------------------- sidebar ----
st.sidebar.header("Filters")

field = st.sidebar.radio(
    "Text field",
    ["message", "title", "both"],
    index=0,
    help="Which free-text field of dim_reviews to analyse.",
)

scores = sorted(s for s in df["review_score"].dropna().unique())
sel_scores = st.sidebar.multiselect(
    "Review score (stars)", scores, default=scores,
    help="Restrict the analysis to reviews with these scores.",
)

max_words = st.sidebar.slider("Word cloud: max words", 50, 400, 200, step=50)


def text_series(frame: pd.DataFrame) -> pd.Series:
    """The chosen text field(s) as one non-empty string Series."""
    if field == "title":
        s = frame["title"]
    elif field == "message":
        s = frame["message"]
    else:  # both
        s = (frame["title"].fillna("") + " " + frame["message"].fillna("")).str.strip()
        s = s.replace("", pd.NA)
    return s.dropna()


# Apply the score filter, then derive the working text series.
fdf = df[df["review_score"].isin(sel_scores)] if sel_scores else df
texts = text_series(fdf)


# -------------------------------------------------------------------- KPIs ----
st.title("💬 Olist Review Text Analysis")
st.caption(
    "Free-text analysis of `dim_reviews` (current review versions) from the Olist gold "
    "mart. Reviews are in Brazilian Portuguese."
)

n_reviews = len(fdf)
n_msg = fdf["message"].notna().sum()
n_title = fdf["title"].notna().sum()
avg_score = fdf["review_score"].mean()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Reviews (filtered)", f"{n_reviews:,}")
c2.metric("With a comment", f"{n_msg:,}", f"{n_msg / max(n_reviews,1):.0%}")
c3.metric("With a title", f"{n_title:,}", f"{n_title / max(n_reviews,1):.0%}")
c4.metric("Avg score", f"{avg_score:.2f} ★")

if texts.empty:
    st.warning("No non-empty text for the current filters. Widen the score selection.")
    st.stop()


# -------------------------------------------------------------- word cloud ----
st.subheader("Word cloud")


@st.cache_data(ttl=3600)
def make_cloud(joined: str, max_words: int) -> "WordCloud":
    return WordCloud(
        width=1200, height=500, background_color="white",
        stopwords=T.STOP, max_words=max_words, collocations=True,
        colormap="viridis",
    ).generate(joined)


# WordCloud does its own tokenizing; we strip accents so variants collapse together.
joined = " ".join(T._strip_accents(t.lower()) for t in texts)
cloud = make_cloud(joined, max_words)
fig, ax = plt.subplots(figsize=(14, 6))
ax.imshow(cloud, interpolation="bilinear")
ax.axis("off")
st.pyplot(fig, use_container_width=True)


# ----------------------------------------------------- top words / bigrams ----
st.subheader("Most frequent terms")
col_w, col_b = st.columns(2)


def bar(items: list[tuple[str, int]], title: str):
    if not items:
        st.info("Not enough text.")
        return
    labels = [w for w, _ in items][::-1]
    values = [c for _, c in items][::-1]
    fig, ax = plt.subplots(figsize=(6, 7))
    ax.barh(labels, values, color="#4f8cff")
    ax.set_title(title)
    ax.tick_params(labelsize=9)
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)


with col_w:
    bar(T.top_words(texts, 20), "Top 20 words")
with col_b:
    bar(T.top_bigrams(texts, 20), "Top 20 bigrams")


# --------------------------------------------------- length vs. sentiment ----
st.subheader("Comment length & review score")

work = fdf.copy()
work["text"] = text_series(work).reindex(work.index)
work["length"] = work["text"].fillna("").str.len()
commented = work[work["length"] > 0]

col_l, col_s = st.columns(2)
with col_l:
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(commented["length"].clip(upper=500), bins=40, color="#34d399")
    ax.set_title("Comment length (chars, clipped at 500)")
    ax.set_xlabel("characters")
    ax.set_ylabel("reviews")
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)

with col_s:
    by_score = commented.groupby("review_score")["length"].mean()
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(by_score.index.astype(int).astype(str), by_score.values, color="#fb6a85")
    ax.set_title("Avg comment length by score")
    ax.set_xlabel("review score (★)")
    ax.set_ylabel("avg characters")
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)


# ---------------------------------------------- negative vs positive clouds ----
st.subheader("What drives bad vs. good reviews")
st.caption("Word clouds for low scores (1–2★) and high scores (4–5★), using the same field.")

col_neg, col_pos = st.columns(2)


def cloud_for(frame: pd.DataFrame, colormap: str):
    s = text_series(frame)
    if s.empty:
        st.info("No text in this score band.")
        return
    joined = " ".join(T._strip_accents(t.lower()) for t in s)
    wc = WordCloud(width=900, height=450, background_color="white",
                   stopwords=T.STOP, max_words=120, colormap=colormap).generate(joined)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    st.pyplot(fig, use_container_width=True)


with col_neg:
    st.markdown("**Low scores (1–2★)**")
    cloud_for(df[df["review_score"].isin([1, 2])], "Reds")
with col_pos:
    st.markdown("**High scores (4–5★)**")
    cloud_for(df[df["review_score"].isin([4, 5])], "Greens")


# ------------------------------------------------------- sample comments ----
with st.expander("Sample comments"):
    sample = commented[["review_score", "title", "message"]].head(30)
    st.dataframe(sample, use_container_width=True, hide_index=True)
