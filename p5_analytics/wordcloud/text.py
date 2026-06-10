"""Text utilities for the Olist review analysis: cleaning, stopwords, n-grams.

Olist reviews are Brazilian **Portuguese**, so the English ``STOPWORDS`` shipped with
``wordcloud`` is not enough. We extend it with a Portuguese stopword list plus a few
domain words that are too generic to be insightful ("produto", "comprei", ...).
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter

from wordcloud import STOPWORDS

# Brazilian-Portuguese stopwords (articles, prepositions, pronouns, common verbs) plus a
# handful of domain-generic words that otherwise dominate every cloud.
_PT_STOPWORDS = {
    "a", "o", "as", "os", "um", "uma", "uns", "umas", "de", "do", "da", "dos", "das",
    "em", "no", "na", "nos", "nas", "por", "pra", "para", "com", "sem", "sob", "sobre",
    "e", "ou", "mas", "que", "se", "porque", "como", "quando", "onde", "qual", "quais",
    "eu", "tu", "ele", "ela", "nos", "vos", "eles", "elas", "voce", "voces", "meu", "minha",
    "seu", "sua", "este", "esta", "isso", "esse", "essa", "aquele", "aquela", "ao", "aos",
    "nao", "sim", "ja", "ainda", "muito", "muita", "muitos", "muitas", "mais", "menos",
    "bem", "mal", "tudo", "nada", "algum", "alguma", "todo", "toda", "todos", "todas",
    "ser", "estar", "ter", "fazer", "foi", "era", "esta", "estao", "sao", "tem", "tinha",
    "ficou", "chegou", "veio", "vou", "vai", "so", "ate", "depois", "antes", "agora",
    "comprei", "produto", "produtos", "compra", "loja", "entrega", "recebi", "recebido",
    "pedido", "item", "itens", "dia", "dias", "prazo", "data",
}

# Final stopword set used for both the word cloud and the frequency charts.
STOP = {w.lower() for w in STOPWORDS} | _PT_STOPWORDS

_TOKEN_RE = re.compile(r"[a-zA-Zá-úÁ-Ú]{3,}")


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    )


def tokens(text: str) -> list[str]:
    """Lowercase, accent-stripped word tokens (length >= 3, no stopwords)."""
    out = []
    for tok in _TOKEN_RE.findall(text.lower()):
        tok = _strip_accents(tok)
        if tok and tok not in STOP:
            out.append(tok)
    return out


def corpus_tokens(texts) -> list[str]:
    """Flatten an iterable of strings into one token list."""
    out: list[str] = []
    for t in texts:
        if isinstance(t, str) and t:
            out.extend(tokens(t))
    return out


def freq(texts) -> Counter:
    """Token-frequency Counter over an iterable of strings."""
    return Counter(corpus_tokens(texts))


def top_words(texts, n: int = 20) -> list[tuple[str, int]]:
    return freq(texts).most_common(n)


def top_bigrams(texts, n: int = 20) -> list[tuple[str, int]]:
    counter: Counter = Counter()
    for t in texts:
        if not isinstance(t, str) or not t:
            continue
        toks = tokens(t)
        counter.update(f"{a} {b}" for a, b in zip(toks, toks[1:]))
    return counter.most_common(n)
