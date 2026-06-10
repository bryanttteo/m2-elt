"""PT->EN translation of review terms via the Google Cloud Translation API.

Used by the app's "English (translated)" language mode so a non-Portuguese reader (e.g.
an English-only exec) can read the word cloud and frequency charts. We translate only
the *unique top terms / bigrams* shown (a few hundred short strings), not every comment,
and memoize per session via ``st.cache_data`` — so the API cost is tiny and stable.

Runtime needs the Cloud Translation API enabled and the service account granted
``roles/cloudtranslate.user`` (see notes/setup.prod.md).
"""
from __future__ import annotations

import streamlit as st

_client = None


def _translate_client():
    global _client
    if _client is None:
        from google.cloud import translate_v2

        _client = translate_v2.Client()
    return _client


@st.cache_data(ttl=86400, show_spinner="Translating terms (PT→EN) ...")
def translate_terms(terms: tuple[str, ...], source: str = "pt", target: str = "en") -> dict:
    """Map each PT term to its lowercased EN translation. Cached by the term tuple."""
    terms = list(terms)
    if not terms:
        return {}
    client = _translate_client()
    out: dict[str, str] = {}
    # The v2 API accepts a batch; chunk to stay well under request limits.
    for i in range(0, len(terms), 100):
        chunk = terms[i:i + 100]
        results = client.translate(
            chunk, source_language=source, target_language=target, format_="text"
        )
        if isinstance(results, dict):  # single-item responses come back un-listed
            results = [results]
        for original, res in zip(chunk, results):
            out[original] = res["translatedText"].lower()
    return out
