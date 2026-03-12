"""Resume Scorer — TF-IDF cosine similarity + optional ONNX embedding support.

Implements: TASK-030 M2 — Scores KB entries against job descriptions using
hand-rolled TF-IDF (stdlib only) with optional ONNX embedding blending.
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from typing import TYPE_CHECKING

from core.jd_analyzer import analyze_jd, normalize_term

if TYPE_CHECKING:
    from config.settings import ResumeReuseConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stopwords (shared with jd_analyzer but duplicated to keep scorer self-contained)
# ---------------------------------------------------------------------------

_STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "shall", "should", "may", "might", "can", "could", "not", "no", "nor",
    "so", "if", "then", "than", "that", "this", "these", "those", "it",
    "its", "we", "our", "you", "your", "they", "their", "he", "she",
    "him", "her", "who", "whom", "which", "what", "when", "where", "how",
    "all", "each", "every", "both", "few", "more", "most", "other", "some",
    "such", "only", "own", "same", "also", "as", "about", "up", "out",
    "into", "over", "after", "before", "between", "through", "during",
    "above", "below", "very", "just", "because", "while", "until",
    "able", "across", "along", "already", "among", "any", "around",
    "etc", "via", "per", "including", "within", "without",
})

_TOKEN_RE = re.compile(r"[a-z][a-z0-9+#./-]*", re.IGNORECASE)


# ---------------------------------------------------------------------------
# TF-IDF Engine (stdlib only)
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    """Tokenize and normalize text into terms."""
    tokens = _TOKEN_RE.findall(text.lower())
    return [normalize_term(t) for t in tokens if normalize_term(t) not in _STOPWORDS and len(t) > 1]


def _term_frequency(tokens: list[str]) -> dict[str, float]:
    """Compute normalized term frequency: count / total_tokens."""
    counts = Counter(tokens)
    total = len(tokens) if tokens else 1
    return {term: count / total for term, count in counts.items()}


def _inverse_document_frequency(
    documents: list[list[str]],
) -> dict[str, float]:
    """Compute IDF: log(N / df) for each term across the corpus."""
    n = len(documents)
    if n == 0:
        return {}

    # Document frequency: how many docs contain each term
    df: Counter[str] = Counter()
    for doc_tokens in documents:
        unique_terms = set(doc_tokens)
        for term in unique_terms:
            df[term] += 1

    # IDF with smoothing: log((N + 1) / (df + 1)) + 1
    return {term: math.log((n + 1) / (freq + 1)) + 1 for term, freq in df.items()}


def _tfidf_vector(
    tf: dict[str, float],
    idf: dict[str, float],
) -> dict[str, float]:
    """Compute TF-IDF vector for a single document."""
    return {term: tf_val * idf.get(term, 0.0) for term, tf_val in tf.items()}


def _cosine_similarity(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    """Compute cosine similarity between two sparse vectors."""
    # Only iterate over shared terms (dot product)
    common_terms = set(vec_a) & set(vec_b)
    if not common_terms:
        return 0.0

    dot = sum(vec_a[t] * vec_b[t] for t in common_terms)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# ONNX Embedding Support (optional)
# ---------------------------------------------------------------------------


def _onnx_available() -> bool:
    """Check if ONNX runtime and tokenizers are installed."""
    try:
        import onnxruntime  # noqa: F401
        import tokenizers  # noqa: F401
        return True
    except ImportError:
        return False


def _onnx_score_entries(
    jd_text: str,
    entries: list[dict],
) -> list[float] | None:
    """Score entries using ONNX embeddings. Returns None if unavailable.

    This is a placeholder for the full ONNX pipeline. When implemented:
    1. Tokenize JD text with HuggingFace tokenizer
    2. Run through ONNX model to get JD embedding
    3. Compare against precomputed entry embeddings (stored in KB)
    4. Return cosine similarity scores
    """
    if not _onnx_available():
        return None

    # Entries without precomputed embeddings can't use ONNX path
    # Check if any entry has an embedding
    has_embeddings = any(
        entry.get("embedding") is not None
        for entry in entries
    )
    if not has_embeddings:
        logger.debug("No precomputed embeddings found, skipping ONNX scoring")
        return None

    # Full implementation deferred to M8 (Performance milestone)
    # For now, return None to fall through to TF-IDF
    logger.debug("ONNX scoring not yet implemented, using TF-IDF fallback")
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def score_kb_entries(
    jd_text: str,
    entries: list[dict],
    config: ResumeReuseConfig | None = None,
) -> list[dict]:
    """Score KB entries against a job description.

    Uses TF-IDF cosine similarity with optional ONNX embedding blending.

    Args:
        jd_text: The job description text.
        entries: List of KB entry dicts (must have 'id', 'text', 'category' keys).
        config: Optional ResumeReuseConfig for min_score and scoring_method.

    Returns:
        List of entry dicts with added 'score' and 'scoring_method' keys,
        sorted by score descending, filtered to >= min_score.
    """
    if not jd_text or not entries:
        return []

    min_score = 0.60
    scoring_method = "auto"
    if config:
        min_score = config.min_score
        scoring_method = config.scoring_method

    # Analyze JD for keyword boosting context
    jd_analysis = analyze_jd(jd_text)

    # TF-IDF scoring
    tfidf_scores = _compute_tfidf_scores(jd_text, entries, jd_analysis)

    # Determine final scores based on method
    method_used = "tfidf"
    final_scores = tfidf_scores

    if scoring_method in ("onnx", "auto"):
        onnx_scores = _onnx_score_entries(jd_text, entries)
        if onnx_scores is not None:
            # Blend: 0.3 * TF-IDF + 0.7 * ONNX
            final_scores = [
                0.3 * tfidf + 0.7 * onnx
                for tfidf, onnx in zip(tfidf_scores, onnx_scores)
            ]
            method_used = "blended"

    # Build results with optional effectiveness weighting (M9)
    results: list[dict] = []
    for entry, score in zip(entries, final_scores):
        # Blend with effectiveness_score if available (M9)
        eff = entry.get("effectiveness_score")
        if eff is not None and eff > 0:
            score = (score * 0.7) + (eff * 0.3)

        if score >= min_score:
            result = dict(entry)
            result["score"] = round(min(score, 1.0), 4)
            result["scoring_method"] = method_used
            results.append(result)

    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)

    logger.info(
        "Scored %d KB entries against JD: %d above threshold (%.2f), method=%s",
        len(entries), len(results), min_score, method_used,
    )
    return results


def compute_tfidf_score(jd_text: str, entry_text: str) -> float:
    """Compute TF-IDF cosine similarity between a JD and a single entry.

    Useful for testing and one-off scoring.
    """
    jd_tokens = _tokenize(jd_text)
    entry_tokens = _tokenize(entry_text)

    if not jd_tokens or not entry_tokens:
        return 0.0

    corpus = [jd_tokens, entry_tokens]
    idf = _inverse_document_frequency(corpus)
    jd_vec = _tfidf_vector(_term_frequency(jd_tokens), idf)
    entry_vec = _tfidf_vector(_term_frequency(entry_tokens), idf)

    return _cosine_similarity(jd_vec, entry_vec)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _compute_tfidf_scores(
    jd_text: str,
    entries: list[dict],
    jd_analysis: dict,
) -> list[float]:
    """Compute TF-IDF cosine similarity for each entry against the JD."""
    # Tokenize JD and all entries
    jd_tokens = _tokenize(jd_text)
    entry_tokens_list = [_tokenize(entry.get("text", "")) for entry in entries]

    if not jd_tokens:
        return [0.0] * len(entries)

    # Build corpus: JD + all entries
    corpus = [jd_tokens] + entry_tokens_list
    idf = _inverse_document_frequency(corpus)

    # TF-IDF vector for JD
    jd_tf = _term_frequency(jd_tokens)
    jd_vec = _tfidf_vector(jd_tf, idf)

    # Apply keyword boost: increase weight for required/preferred terms
    required_terms = set(jd_analysis.get("required_keywords", []))
    preferred_terms = set(jd_analysis.get("preferred_keywords", []))
    tech_terms = set(jd_analysis.get("tech_terms", []))

    # Score each entry
    scores: list[float] = []
    for entry_tokens in entry_tokens_list:
        if not entry_tokens:
            scores.append(0.0)
            continue

        entry_tf = _term_frequency(entry_tokens)
        entry_vec = _tfidf_vector(entry_tf, idf)

        # Base cosine similarity
        base_score = _cosine_similarity(jd_vec, entry_vec)

        # Keyword match bonus (additive, capped)
        entry_terms = set(entry_tokens)
        req_matches = len(entry_terms & required_terms)
        pref_matches = len(entry_terms & preferred_terms)
        tech_matches = len(entry_terms & tech_terms)

        # Bonus: up to 0.15 for required, 0.05 for preferred, 0.05 for tech
        req_bonus = min(req_matches * 0.03, 0.15) if required_terms else 0.0
        pref_bonus = min(pref_matches * 0.02, 0.05) if preferred_terms else 0.0
        tech_bonus = min(tech_matches * 0.01, 0.05) if tech_terms else 0.0

        final = min(base_score + req_bonus + pref_bonus + tech_bonus, 1.0)
        scores.append(final)

    return scores
