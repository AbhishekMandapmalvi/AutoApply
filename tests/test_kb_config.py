"""Tests for config/settings.py KB config models — TASK-030 M1.

Tests ResumeReuseConfig, LatexConfig, and AppConfig backward compatibility.
"""

import json

from config.settings import AppConfig, LatexConfig, ResumeReuseConfig


class TestResumeReuseConfig:
    """Tests for ResumeReuseConfig model."""

    def test_defaults(self):
        """Default values are sensible."""
        cfg = ResumeReuseConfig()
        assert cfg.enabled is True
        assert cfg.min_score == 0.60
        assert cfg.min_experience_bullets == 6
        assert cfg.scoring_method == "auto"
        assert cfg.cover_letter_strategy == "generate"

    def test_custom_values(self):
        """Custom values are accepted."""
        cfg = ResumeReuseConfig(
            enabled=False,
            min_score=0.75,
            min_experience_bullets=4,
            scoring_method="tfidf",
        )
        assert cfg.enabled is False
        assert cfg.min_score == 0.75


class TestLatexConfig:
    """Tests for LatexConfig model."""

    def test_defaults(self):
        """Default values are sensible."""
        cfg = LatexConfig()
        assert cfg.template == "classic"
        assert cfg.font_family == "helvetica"
        assert cfg.font_size == 11
        assert cfg.margin == "0.75in"

    def test_custom_template(self):
        """Custom template name is accepted."""
        cfg = LatexConfig(template="modern", font_size=10)
        assert cfg.template == "modern"
        assert cfg.font_size == 10


class TestAppConfigBackwardCompat:
    """Tests for AppConfig with new fields."""

    def test_missing_reuse_config_uses_defaults(self):
        """Old config.json without resume_reuse/latex fields works."""
        data = {
            "profile": {
                "first_name": "John",
                "last_name": "Doe",
                "email": "john@example.com",
                "phone": "555-1234",
                "city": "SF",
                "state": "CA",
                "bio": "Engineer",
            },
            "search_criteria": {
                "job_titles": ["Engineer"],
                "locations": ["SF"],
            },
        }
        config = AppConfig(**data)
        assert config.resume_reuse.enabled is True
        assert config.latex.template == "classic"

    def test_explicit_reuse_config(self):
        """Explicit resume_reuse config is respected."""
        data = {
            "profile": {
                "first_name": "John",
                "last_name": "Doe",
                "email": "john@example.com",
                "phone": "555-1234",
                "city": "SF",
                "state": "CA",
                "bio": "Engineer",
            },
            "search_criteria": {
                "job_titles": ["Engineer"],
                "locations": ["SF"],
            },
            "resume_reuse": {
                "enabled": False,
                "min_score": 0.80,
            },
            "latex": {
                "template": "modern",
            },
        }
        config = AppConfig(**data)
        assert config.resume_reuse.enabled is False
        assert config.resume_reuse.min_score == 0.80
        assert config.latex.template == "modern"

    def test_serialization_roundtrip(self):
        """Config serializes and deserializes correctly."""
        data = {
            "profile": {
                "first_name": "John",
                "last_name": "Doe",
                "email": "john@example.com",
                "phone": "555-1234",
                "city": "SF",
                "state": "CA",
                "bio": "Engineer",
            },
            "search_criteria": {
                "job_titles": ["Engineer"],
                "locations": ["SF"],
            },
            "resume_reuse": {"min_score": 0.70},
            "latex": {"template": "academic", "font_size": 12},
        }
        config = AppConfig(**data)
        dumped = json.loads(json.dumps(config.model_dump()))

        config2 = AppConfig(**dumped)
        assert config2.resume_reuse.min_score == 0.70
        assert config2.latex.template == "academic"
        assert config2.latex.font_size == 12
