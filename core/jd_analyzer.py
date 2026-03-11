"""Job Description Analyzer — keyword extraction, n-grams, synonym normalization.

Implements: TASK-030 M2 — Parses job description text to extract structured
keyword data for scoring KB entries against job requirements.
"""

from __future__ import annotations

import logging
import re
from collections import Counter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Synonym normalization — maps common aliases to canonical tech terms
# ---------------------------------------------------------------------------

SYNONYM_MAP: dict[str, str] = {
    # Languages
    "js": "javascript",
    "ts": "typescript",
    "py": "python",
    "golang": "go",
    "c++": "cpp",
    "c#": "csharp",
    "obj-c": "objective-c",
    "objective c": "objective-c",
    # Frameworks / libraries
    "react.js": "react",
    "reactjs": "react",
    "node.js": "nodejs",
    "vue.js": "vue",
    "vuejs": "vue",
    "next.js": "nextjs",
    "nuxt.js": "nuxtjs",
    "express.js": "express",
    "expressjs": "express",
    "angular.js": "angularjs",
    "spring boot": "springboot",
    "ruby on rails": "rails",
    "asp.net": "aspnet",
    ".net": "dotnet",
    # Cloud / DevOps
    "amazon web services": "aws",
    "google cloud platform": "gcp",
    "google cloud": "gcp",
    "microsoft azure": "azure",
    "k8s": "kubernetes",
    "ci/cd": "cicd",
    "ci cd": "cicd",
    # Databases
    "postgres": "postgresql",
    "mongo": "mongodb",
    "dynamo": "dynamodb",
    "dynamodb": "dynamodb",
    "ms sql": "mssql",
    "sql server": "mssql",
    # ML / Data
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "dl": "deep learning",
    "nlp": "natural language processing",
    "cv": "computer vision",
    "scikit-learn": "sklearn",
    "sci-kit learn": "sklearn",
    "scikit learn": "sklearn",
    "tensor flow": "tensorflow",
    "py torch": "pytorch",
}

# ---------------------------------------------------------------------------
# Tech dictionary — known technology terms for extraction
# ---------------------------------------------------------------------------

TECH_TERMS: frozenset[str] = frozenset({
    # Languages
    "python", "javascript", "typescript", "java", "go", "rust", "cpp",
    "csharp", "ruby", "php", "swift", "kotlin", "scala", "r", "matlab",
    "perl", "objective-c", "dart", "lua", "haskell", "elixir", "clojure",
    # Frontend
    "react", "vue", "angular", "svelte", "nextjs", "nuxtjs", "html", "css",
    "sass", "less", "tailwind", "bootstrap", "webpack", "vite", "redux",
    "graphql", "rest", "grpc",
    # Backend
    "nodejs", "express", "django", "flask", "fastapi", "rails",
    "springboot", "aspnet", "dotnet", "laravel", "gin", "fiber",
    # Databases
    "postgresql", "mysql", "sqlite", "mongodb", "redis", "elasticsearch",
    "dynamodb", "cassandra", "neo4j", "mssql", "oracle",
    # Cloud / DevOps
    "aws", "gcp", "azure", "docker", "kubernetes", "terraform",
    "ansible", "jenkins", "cicd", "github actions", "gitlab ci",
    "cloudformation", "pulumi", "helm", "prometheus", "grafana",
    # Data / ML
    "spark", "kafka", "airflow", "dbt", "snowflake", "bigquery",
    "redshift", "tensorflow", "pytorch", "sklearn", "pandas", "numpy",
    "machine learning", "deep learning", "natural language processing",
    "computer vision", "artificial intelligence",
    # Other
    "git", "linux", "agile", "scrum", "jira", "confluence",
})

# ---------------------------------------------------------------------------
# Section header patterns — detect JD structure
# ---------------------------------------------------------------------------

_SECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("requirements", re.compile(
        r"(?:requirements?|qualifications?|what you.?ll need|must have|minimum)",
        re.IGNORECASE,
    )),
    ("preferred", re.compile(
        r"(?:prefer(?:red)?|nice to have|bonus|desired|plus|ideal)",
        re.IGNORECASE,
    )),
    ("responsibilities", re.compile(
        r"(?:responsibilit|what you.?ll do|about the role|duties|role overview)",
        re.IGNORECASE,
    )),
    ("benefits", re.compile(
        r"(?:benefits?|perks?|compensation|what we offer)",
        re.IGNORECASE,
    )),
    ("about", re.compile(
        r"(?:about (?:us|the company)|who we are|our (?:mission|story))",
        re.IGNORECASE,
    )),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyze_jd(text: str) -> dict:
    """Analyze a job description and extract structured keyword data.

    Returns:
        {
            "keywords": list[str],          # all extracted keywords (normalized)
            "required_keywords": list[str],  # keywords from requirements section
            "preferred_keywords": list[str], # keywords from preferred section
            "tech_terms": list[str],         # recognized technology terms
            "ngrams": list[str],             # 2-3 word phrases
            "sections": dict[str, str],      # detected sections
            "keyword_counts": dict[str, int],# frequency counts
        }
    """
    if not text or not text.strip():
        return {
            "keywords": [],
            "required_keywords": [],
            "preferred_keywords": [],
            "tech_terms": [],
            "ngrams": [],
            "sections": {},
            "keyword_counts": {},
        }

    sections = _detect_sections(text)
    all_keywords = _extract_keywords(text)
    tech = _extract_tech_terms(text)
    ngrams = _extract_ngrams(text, n_range=(2, 3))

    # Extract from requirements/preferred sections specifically
    req_text = sections.get("requirements", "")
    pref_text = sections.get("preferred", "")
    required_kw = _extract_keywords(req_text) if req_text else []
    preferred_kw = _extract_keywords(pref_text) if pref_text else []

    # Merge tech terms into keyword lists
    combined = list(dict.fromkeys(all_keywords + tech))
    req_combined = list(dict.fromkeys(required_kw + _extract_tech_terms(req_text)))
    pref_combined = list(dict.fromkeys(preferred_kw + _extract_tech_terms(pref_text)))

    # Count frequencies
    keyword_counts = dict(Counter(combined))

    return {
        "keywords": combined,
        "required_keywords": req_combined,
        "preferred_keywords": pref_combined,
        "tech_terms": tech,
        "ngrams": ngrams,
        "sections": {k: v for k, v in sections.items() if v},
        "keyword_counts": keyword_counts,
    }


def normalize_term(term: str) -> str:
    """Normalize a term using the synonym map."""
    lowered = term.strip().lower()
    return SYNONYM_MAP.get(lowered, lowered)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Stopwords — common English words to exclude from keyword extraction
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


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase words."""
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def _extract_keywords(text: str) -> list[str]:
    """Extract meaningful keywords from text (stop-word filtered, normalized)."""
    tokens = _tokenize(text)
    keywords: list[str] = []
    seen: set[str] = set()
    for tok in tokens:
        normalized = normalize_term(tok)
        if normalized in _STOPWORDS or len(normalized) < 2:
            continue
        if normalized not in seen:
            seen.add(normalized)
            keywords.append(normalized)
    return keywords


def _extract_tech_terms(text: str) -> list[str]:
    """Extract recognized technology terms from text."""
    lowered = text.lower()
    found: list[str] = []
    seen: set[str] = set()

    # Check multi-word terms first
    for term in TECH_TERMS:
        if " " in term and term in lowered and term not in seen:
            found.append(term)
            seen.add(term)

    # Check single-word terms via tokenization
    tokens = set(_tokenize(text))
    for tok in tokens:
        normalized = normalize_term(tok)
        if normalized in TECH_TERMS and normalized not in seen:
            found.append(normalized)
            seen.add(normalized)

    return sorted(found)


def _extract_ngrams(text: str, n_range: tuple[int, int] = (2, 3)) -> list[str]:
    """Extract n-gram phrases from text."""
    tokens = _tokenize(text)
    # Filter stopwords for n-gram context
    filtered = [t for t in tokens if normalize_term(t) not in _STOPWORDS and len(t) > 1]

    ngrams: list[str] = []
    seen: set[str] = set()

    for n in range(n_range[0], n_range[1] + 1):
        for i in range(len(filtered) - n + 1):
            normalized = " ".join(normalize_term(t) for t in filtered[i:i + n])
            if normalized not in seen:
                seen.add(normalized)
                ngrams.append(normalized)

    return ngrams


def _detect_sections(text: str) -> dict[str, str]:
    """Detect JD sections by header patterns. Returns section_name -> content."""
    lines = text.split("\n")
    sections: dict[str, str] = {}
    current_section: str | None = None
    current_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        matched_section = None

        for section_name, pattern in _SECTION_PATTERNS:
            if pattern.search(stripped):
                # Only treat as header if it's a short line (likely a heading)
                if len(stripped) < 80:
                    matched_section = section_name
                    break

        if matched_section:
            # Save previous section
            if current_section:
                sections[current_section] = "\n".join(current_lines).strip()
            current_section = matched_section
            current_lines = []
        elif current_section:
            current_lines.append(line)

    # Save last section
    if current_section:
        sections[current_section] = "\n".join(current_lines).strip()

    return sections
