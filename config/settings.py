"""Application configuration and settings models.

Implements: FR-001 (data directory), FR-003 (configuration model),
            NFR-QW1 (keyring integration).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import BaseModel, model_validator

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyring helpers — lazy-checked, graceful fallback to plaintext
# ---------------------------------------------------------------------------

_keyring_available: bool | None = None  # lazy-init sentinel
KEYRING_SERVICE = "autoapply"
KEYRING_KEY_NAME = "llm_api_key"


def _check_keyring() -> bool:
    """Return True if the OS keyring backend is usable. Result is cached."""
    global _keyring_available
    if _keyring_available is not None:
        return _keyring_available
    try:
        import keyring
        keyring.get_password(KEYRING_SERVICE, "__probe__")
        _keyring_available = True
    except Exception:
        _logger.warning("keyring unavailable — API key stored in plaintext config")
        _keyring_available = False
    return _keyring_available


class UserProfile(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone_country_code: str = "+1"
    phone: str
    address_line1: str = ""
    address_line2: str = ""
    city: str
    state: str
    zip_code: str = ""
    country: str = "United States"
    bio: str
    linkedin_url: str | None = None
    portfolio_url: str | None = None
    fallback_resume_path: str | None = None
    screening_answers: dict = {}

    # Backward-compatible property — used by AI engine prompts and Lever/Indeed
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    # Backward-compatible property — formatted location string
    @property
    def location(self) -> str:
        parts = [self.city, self.state]
        loc = ", ".join(p for p in parts if p)
        if self.country and self.country != "United States":
            loc = f"{loc}, {self.country}" if loc else self.country
        return loc

    # Full phone with country code
    @property
    def phone_full(self) -> str:
        if self.phone_country_code and not self.phone.startswith("+"):
            return f"{self.phone_country_code}{self.phone}"
        return self.phone

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_fields(cls, data):
        """Accept old config format with full_name and location strings."""
        if isinstance(data, dict):
            # Migrate full_name → first_name + last_name
            if "full_name" in data and "first_name" not in data:
                parts = data.pop("full_name", "").split(None, 1)
                data["first_name"] = parts[0] if parts else ""
                data["last_name"] = parts[1] if len(parts) > 1 else ""
            # Migrate location → city + state
            if "location" in data and "city" not in data:
                loc = data.pop("location", "")
                parts = [p.strip() for p in loc.split(",")]
                data["city"] = parts[0] if parts else ""
                data["state"] = parts[1] if len(parts) > 1 else ""
                if len(parts) > 2:
                    data["country"] = parts[2]
        return data


class SearchCriteria(BaseModel):
    job_titles: list[str]
    locations: list[str]
    remote_only: bool = False
    salary_min: int | None = None
    keywords_include: list[str] = []
    keywords_exclude: list[str] = []
    experience_levels: list[str] = ["mid", "senior"]


class ScheduleConfig(BaseModel):
    enabled: bool = False
    days_of_week: list[str] = ["mon", "tue", "wed", "thu", "fri"]
    start_time: str = "09:00"  # HH:MM in 24-hour local time
    end_time: str = "17:00"    # HH:MM in 24-hour local time


class LLMConfig(BaseModel):
    provider: str = ""  # "anthropic" | "openai" | "google" | "deepseek"
    api_key: str = ""
    model: str = ""  # Empty = use default for provider


class ResumeReuseConfig(BaseModel):
    """Configuration for smart resume reuse via Knowledge Base assembly."""
    enabled: bool = True
    min_score: float = 0.0
    min_experience_bullets: int = 6
    scoring_method: str = "auto"  # "tfidf" | "onnx" | "auto"
    cover_letter_strategy: str = "generate"  # "generate" | "template"


class LatexConfig(BaseModel):
    """Configuration for LaTeX resume compilation."""
    template: str = "classic"  # template name in templates/latex/
    font_family: str = "helvetica"  # helvetica, times, palatino
    font_size: int = 11  # 10, 11, 12
    margin: str = "0.75in"


class BotConfig(BaseModel):
    enabled_platforms: list[str] = ["linkedin", "indeed"]
    min_match_score: int = 75
    max_applications_per_day: int = 50
    delay_between_applications_seconds: int = 45
    search_interval_seconds: int = 1800
    apply_mode: str = "full_auto"  # "full_auto" | "review" | "watch"
    watch_mode: bool = False  # Deprecated: use apply_mode instead
    cover_letter_enabled: bool = True
    cover_letter_template: str = ""
    schedule: ScheduleConfig = ScheduleConfig()


class AppConfig(BaseModel):
    profile: UserProfile
    search_criteria: SearchCriteria
    bot: BotConfig = BotConfig()
    llm: LLMConfig = LLMConfig()
    resume_reuse: ResumeReuseConfig = ResumeReuseConfig()
    latex: LatexConfig = LatexConfig()
    company_blacklist: list[str] = []
    version: str = "2.0"


def get_data_dir() -> Path:
    return Path.home() / ".autoapply"


def load_config() -> AppConfig | None:
    config_path = get_data_dir() / "config.json"
    if not config_path.exists():
        return None
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    config = AppConfig(**data)

    # Retrieve API key from keyring if available
    if _check_keyring():
        import keyring

        stored_key = keyring.get_password(KEYRING_SERVICE, KEYRING_KEY_NAME)
        if stored_key:
            config.llm.api_key = stored_key
        elif config.llm.api_key:
            # Migration: move plaintext key into keyring
            keyring.set_password(
                KEYRING_SERVICE, KEYRING_KEY_NAME, config.llm.api_key
            )
            _save_config_raw(config, strip_api_key=True)
            _logger.info("Migrated API key from config.json to OS keyring")

    return config


def save_config(config: AppConfig) -> None:
    # Store API key in keyring if possible
    if config.llm.api_key and _check_keyring():
        import keyring

        keyring.set_password(
            KEYRING_SERVICE, KEYRING_KEY_NAME, config.llm.api_key
        )

    _save_config_raw(config, strip_api_key=_check_keyring())


def _save_config_raw(config: AppConfig, strip_api_key: bool = False) -> None:
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    config_path = data_dir / "config.json"
    dump = config.model_dump()
    if strip_api_key:
        dump.get("llm", {})["api_key"] = ""
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(dump, f, indent=2)


def is_first_run() -> bool:
    return not (get_data_dir() / "config.json").exists()
