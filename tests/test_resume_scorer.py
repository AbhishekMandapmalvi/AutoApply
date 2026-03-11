"""Tests for core/resume_scorer.py and core/jd_analyzer.py — TASK-030 M2.

Tests TF-IDF scoring, keyword extraction, synonym normalization,
ONNX mock support, score blending, and JD section detection.
"""

import json
from unittest.mock import patch

import pytest

from core.jd_analyzer import analyze_jd, normalize_term
from core.resume_scorer import (
    _cosine_similarity,
    _inverse_document_frequency,
    _term_frequency,
    _tokenize,
    compute_tfidf_score,
    score_kb_entries,
)
from db.database import Database

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db(tmp_path):
    """Create a fresh database for each test."""
    return Database(tmp_path / "test.db")


@pytest.fixture
def sample_jd():
    """A realistic backend engineer job description."""
    return """
    Senior Backend Engineer

    About the Role:
    We are looking for a Senior Backend Engineer to design and build scalable
    microservices using Python, Flask, and PostgreSQL.

    Requirements:
    - 5+ years experience with Python
    - Strong experience with Flask or Django
    - PostgreSQL and Redis
    - Docker and Kubernetes
    - CI/CD pipelines (GitHub Actions preferred)
    - RESTful API design
    - Experience with AWS (EC2, S3, Lambda)

    Nice to Have:
    - Experience with Kafka or RabbitMQ
    - Knowledge of Terraform
    - GraphQL experience
    - Machine Learning exposure

    Responsibilities:
    - Design and implement RESTful APIs
    - Optimize database queries for performance
    - Write comprehensive unit and integration tests
    - Mentor junior developers
    """


@pytest.fixture
def sample_entries():
    """Sample KB entries for scoring."""
    return [
        {
            "id": 1,
            "category": "experience",
            "text": "Built scalable microservices using Python and Flask, handling 10K+ requests/second with PostgreSQL backend",
            "subsection": "Senior Engineer — TechCorp (2021-2024)",
            "job_types": json.dumps(["backend"]),
        },
        {
            "id": 2,
            "category": "experience",
            "text": "Designed CI/CD pipelines with GitHub Actions and Docker, reducing deployment time by 60%",
            "subsection": "DevOps Engineer — CloudInc (2020-2021)",
            "job_types": json.dumps(["devops", "backend"]),
        },
        {
            "id": 3,
            "category": "skill",
            "text": "Python, Flask, Django, PostgreSQL, Redis, Docker, Kubernetes, AWS",
            "subsection": None,
            "job_types": json.dumps(["backend", "devops"]),
        },
        {
            "id": 4,
            "category": "experience",
            "text": "Created interactive data visualizations using D3.js and React for financial dashboards",
            "subsection": "Frontend Dev — FinTech (2019-2020)",
            "job_types": json.dumps(["frontend"]),
        },
        {
            "id": 5,
            "category": "education",
            "text": "M.S. Computer Science, Stanford University, 2019",
            "subsection": None,
            "job_types": json.dumps(["general"]),
        },
    ]


@pytest.fixture
def reuse_config():
    """Create a ResumeReuseConfig for testing."""
    from config.settings import ResumeReuseConfig
    return ResumeReuseConfig(min_score=0.30, scoring_method="auto")


# ---------------------------------------------------------------------------
# JD Analyzer Tests
# ---------------------------------------------------------------------------


class TestJDAnalyzer:
    """Tests for job description analysis."""

    def test_analyze_empty_text(self):
        """Empty text returns empty analysis."""
        result = analyze_jd("")
        assert result["keywords"] == []
        assert result["tech_terms"] == []
        assert result["sections"] == {}

    def test_analyze_none_text(self):
        """None text returns empty analysis."""
        result = analyze_jd(None)
        assert result["keywords"] == []

    def test_analyze_extracts_tech_terms(self, sample_jd):
        """Should find known tech terms in JD."""
        result = analyze_jd(sample_jd)
        tech = result["tech_terms"]
        assert "python" in tech
        assert "flask" in tech
        assert "postgresql" in tech
        assert "docker" in tech
        assert "kubernetes" in tech

    def test_analyze_detects_sections(self, sample_jd):
        """Should detect requirements, preferred, and responsibilities sections."""
        result = analyze_jd(sample_jd)
        assert "requirements" in result["sections"]
        assert "preferred" in result["sections"]
        assert "responsibilities" in result["sections"]

    def test_analyze_required_keywords(self, sample_jd):
        """Required keywords should come from requirements section."""
        result = analyze_jd(sample_jd)
        req = result["required_keywords"]
        # Python should be in requirements
        assert "python" in req

    def test_analyze_preferred_keywords(self, sample_jd):
        """Preferred keywords should come from nice-to-have section."""
        result = analyze_jd(sample_jd)
        pref = result["preferred_keywords"]
        assert "terraform" in pref

    def test_analyze_ngrams(self, sample_jd):
        """Should extract 2-3 word n-grams."""
        result = analyze_jd(sample_jd)
        assert len(result["ngrams"]) > 0
        # All n-grams should be multi-word
        for gram in result["ngrams"]:
            assert " " in gram

    def test_normalize_synonym(self):
        """Synonym normalization should map aliases."""
        assert normalize_term("JS") == "javascript"
        assert normalize_term("ts") == "typescript"
        assert normalize_term("k8s") == "kubernetes"
        assert normalize_term("postgres") == "postgresql"
        assert normalize_term("ci/cd") == "cicd"

    def test_normalize_unknown_passes_through(self):
        """Unknown terms pass through unchanged (lowered)."""
        assert normalize_term("UnknownTerm") == "unknownterm"
        assert normalize_term("Python") == "python"

    def test_keyword_counts(self, sample_jd):
        """Should count keyword frequencies."""
        result = analyze_jd(sample_jd)
        counts = result["keyword_counts"]
        assert isinstance(counts, dict)
        # Python appears multiple times in the JD
        assert "python" in counts


# ---------------------------------------------------------------------------
# TF-IDF Engine Tests
# ---------------------------------------------------------------------------


class TestTFIDF:
    """Tests for TF-IDF scoring internals."""

    def test_tokenize_basic(self):
        """Tokenize should lowercase and filter stopwords."""
        tokens = _tokenize("The quick Python developer builds APIs with Flask")
        assert "python" in tokens
        assert "flask" in tokens
        assert "the" not in tokens
        assert "with" not in tokens

    def test_tokenize_empty(self):
        """Tokenize handles empty/whitespace input."""
        assert _tokenize("") == []
        assert _tokenize("   ") == []

    def test_tokenize_normalizes_synonyms(self):
        """Tokenize should normalize known synonyms."""
        tokens = _tokenize("Experience with JS and k8s")
        assert "javascript" in tokens
        assert "kubernetes" in tokens

    def test_term_frequency(self):
        """TF should produce normalized counts."""
        tf = _term_frequency(["python", "flask", "python", "api"])
        assert tf["python"] == pytest.approx(2 / 4)
        assert tf["flask"] == pytest.approx(1 / 4)
        assert tf["api"] == pytest.approx(1 / 4)

    def test_term_frequency_empty(self):
        """TF of empty list returns empty dict."""
        assert _term_frequency([]) == {}

    def test_idf_basic(self):
        """IDF should be higher for rare terms."""
        docs = [
            ["python", "flask"],
            ["python", "django"],
            ["python", "react"],
        ]
        idf = _inverse_document_frequency(docs)
        # "python" appears in all 3 docs → lower IDF
        # "flask" appears in 1 doc → higher IDF
        assert idf["flask"] > idf["python"]

    def test_idf_empty_corpus(self):
        """IDF of empty corpus returns empty dict."""
        assert _inverse_document_frequency([]) == {}

    def test_cosine_similarity_identical(self):
        """Identical vectors should have similarity ~1.0."""
        vec = {"python": 1.0, "flask": 0.5}
        assert _cosine_similarity(vec, vec) == pytest.approx(1.0)

    def test_cosine_similarity_orthogonal(self):
        """Non-overlapping vectors should have similarity 0.0."""
        vec_a = {"python": 1.0}
        vec_b = {"java": 1.0}
        assert _cosine_similarity(vec_a, vec_b) == 0.0

    def test_cosine_similarity_partial(self):
        """Partial overlap should give 0 < sim < 1."""
        vec_a = {"python": 1.0, "flask": 0.5, "aws": 0.3}
        vec_b = {"python": 0.8, "java": 0.5, "aws": 0.6}
        sim = _cosine_similarity(vec_a, vec_b)
        assert 0.0 < sim < 1.0

    def test_compute_tfidf_score_similar(self):
        """Similar texts should have a positive score."""
        jd = "Python backend engineer with Flask and PostgreSQL experience"
        entry = "Built backend APIs using Python and Flask with PostgreSQL database"
        score = compute_tfidf_score(jd, entry)
        assert score > 0.3

    def test_compute_tfidf_score_dissimilar(self):
        """Dissimilar texts should have a low score."""
        jd = "Python backend engineer with Flask and PostgreSQL"
        entry = "Designed logos and branding for retail marketing campaigns"
        score = compute_tfidf_score(jd, entry)
        assert score < 0.2

    def test_compute_tfidf_score_empty(self):
        """Empty inputs return 0."""
        assert compute_tfidf_score("", "some text") == 0.0
        assert compute_tfidf_score("some text", "") == 0.0


# ---------------------------------------------------------------------------
# Score KB Entries Tests
# ---------------------------------------------------------------------------


class TestScoreKBEntries:
    """Tests for the main score_kb_entries() function."""

    def test_score_returns_sorted(self, sample_jd, sample_entries, reuse_config):
        """Results should be sorted by score descending."""
        results = score_kb_entries(sample_jd, sample_entries, reuse_config)
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_score_filters_below_threshold(self, sample_jd, sample_entries):
        """Entries below min_score should be filtered out."""
        from config.settings import ResumeReuseConfig
        strict_config = ResumeReuseConfig(min_score=0.90, scoring_method="tfidf")
        results = score_kb_entries(sample_jd, sample_entries, strict_config)
        for r in results:
            assert r["score"] >= 0.90

    def test_score_relevant_entries_rank_higher(self, sample_jd, sample_entries, reuse_config):
        """Backend entries should rank higher than frontend for a backend JD."""
        results = score_kb_entries(sample_jd, sample_entries, reuse_config)
        if len(results) >= 2:
            # The Python/Flask entry (id=1) or skill entry (id=3) should
            # rank higher than the D3.js/React entry (id=4)
            ids_ranked = [r["id"] for r in results]
            backend_ids = {1, 2, 3}
            frontend_id = 4
            if frontend_id in ids_ranked:
                frontend_rank = ids_ranked.index(frontend_id)
                # At least one backend entry should rank above frontend
                assert any(
                    ids_ranked.index(bid) < frontend_rank
                    for bid in backend_ids
                    if bid in ids_ranked
                )

    def test_score_includes_method(self, sample_jd, sample_entries, reuse_config):
        """Results should include scoring_method field."""
        results = score_kb_entries(sample_jd, sample_entries, reuse_config)
        for r in results:
            assert "scoring_method" in r
            assert r["scoring_method"] in ("tfidf", "blended")

    def test_score_empty_jd(self, sample_entries, reuse_config):
        """Empty JD returns no results."""
        assert score_kb_entries("", sample_entries, reuse_config) == []

    def test_score_empty_entries(self, sample_jd, reuse_config):
        """Empty entries list returns no results."""
        assert score_kb_entries(sample_jd, [], reuse_config) == []

    def test_score_preserves_entry_fields(self, sample_jd, sample_entries, reuse_config):
        """Scored results should preserve original entry fields plus score."""
        results = score_kb_entries(sample_jd, sample_entries, reuse_config)
        for r in results:
            assert "id" in r
            assert "category" in r
            assert "text" in r
            assert "score" in r
            assert isinstance(r["score"], float)

    def test_score_none_config_uses_defaults(self, sample_jd, sample_entries):
        """None config should use default min_score=0.60."""
        results = score_kb_entries(sample_jd, sample_entries, config=None)
        for r in results:
            assert r["score"] >= 0.60


# ---------------------------------------------------------------------------
# ONNX Blending Tests (mocked)
# ---------------------------------------------------------------------------


class TestONNXBlending:
    """Tests for ONNX score blending (mocked)."""

    def test_onnx_unavailable_falls_to_tfidf(self, sample_jd, sample_entries, reuse_config):
        """When ONNX is not installed, should use TF-IDF only."""
        with patch("core.resume_scorer._onnx_available", return_value=False):
            results = score_kb_entries(sample_jd, sample_entries, reuse_config)
            for r in results:
                assert r["scoring_method"] == "tfidf"

    def test_onnx_blending_when_available(self, sample_jd, sample_entries, reuse_config):
        """When ONNX scores are available, should blend 0.3*tfidf + 0.7*onnx."""
        fake_onnx_scores = [0.9, 0.8, 0.95, 0.3, 0.4]

        with patch("core.resume_scorer._onnx_score_entries", return_value=fake_onnx_scores):
            results = score_kb_entries(sample_jd, sample_entries, reuse_config)
            for r in results:
                assert r["scoring_method"] == "blended"

    def test_tfidf_method_skips_onnx(self, sample_jd, sample_entries):
        """scoring_method='tfidf' should skip ONNX entirely."""
        from config.settings import ResumeReuseConfig
        config = ResumeReuseConfig(min_score=0.30, scoring_method="tfidf")

        with patch("core.resume_scorer._onnx_score_entries") as mock_onnx:
            results = score_kb_entries(sample_jd, sample_entries, config)
            mock_onnx.assert_not_called()
            for r in results:
                assert r["scoring_method"] == "tfidf"


# ---------------------------------------------------------------------------
# Section Detection Tests
# ---------------------------------------------------------------------------


class TestSectionDetection:
    """Tests for JD section detection."""

    def test_detect_requirements_section(self):
        """Should detect 'Requirements' header."""
        text = "About Us\nWe are great.\n\nRequirements:\n- Python\n- Flask"
        result = analyze_jd(text)
        assert "requirements" in result["sections"]
        assert "Python" in result["sections"]["requirements"]

    def test_detect_nice_to_have(self):
        """Should detect 'Nice to Have' as preferred section."""
        text = "Requirements:\n- Python\n\nNice to Have:\n- Terraform\n- GraphQL"
        result = analyze_jd(text)
        assert "preferred" in result["sections"]
        assert "Terraform" in result["sections"]["preferred"]

    def test_detect_responsibilities(self):
        """Should detect 'Responsibilities' header."""
        text = "Responsibilities:\n- Design APIs\n- Write tests"
        result = analyze_jd(text)
        assert "responsibilities" in result["sections"]

    def test_no_sections_in_flat_text(self):
        """Plain text without headers should have no sections."""
        text = "We need a Python developer who knows Flask and PostgreSQL."
        result = analyze_jd(text)
        assert result["sections"] == {}
