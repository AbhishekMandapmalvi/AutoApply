# Smart Resume Reuse with LLM + ReportLab Knowledge Base — Implementation Plan (TASK-030)

**Status**: DRAFT v0.2 — refined pipeline with document upload + LLM extraction
**Date**: 2026-03-11

---

## Context

Currently, the bot generates a new resume via cloud LLM for **every** job application (2 API calls each). This is expensive and redundant for similar roles. The current experience file system (.txt files) requires users to manually structure their career content.

**New approach**: A **Knowledge Base** pipeline where:
1. User uploads raw career documents (PDF, DOCX, TXT, MD) — resumes, project descriptions, anything
2. Cloud LLM processes each upload **once** → extracts clean, professional bullet points categorized by resume section type and job type
3. Knowledge base stores these polished entries locally in SQLite
4. When a new job arrives, system scores KB entries against JD, sends best entries to LLM with strict "only use provided data" instructions, renders PDF via ReportLab
5. No PDFs are stored — only KB entry IDs. Resumes are rendered on demand from IDs.

**Cost model**: LLM is called once per document upload for extraction, and once per resume assembly for generation. The LLM is constrained to use ONLY KB data — no hallucinated experiences.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     DOCUMENT UPLOAD PIPELINE                     │
│                                                                  │
│  User uploads    ─→  Extract text   ─→  Cloud LLM     ─→  Store │
│  PDF/DOCX/TXT/MD    (PyPDF2/docx/     (one-time call)    in KB  │
│                      raw read)         Categorize &             │
│                                        polish bullets           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     KNOWLEDGE BASE (SQLite)                      │
│                                                                  │
│  ┌───────────┐ ┌──────────┐ ┌───────────┐ ┌──────────────────┐ │
│  │Experience │ │ Skills   │ │ Education │ │ Projects/Certs/  │ │
│  │ bullets   │ │ groups   │ │ entries   │ │ Summaries        │ │
│  └───────────┘ └──────────┘ └───────────┘ └──────────────────┘ │
│                                                                  │
│  Each entry tagged with: job_types[], keywords[], source_doc    │
└──────────────────────┬──────────────────────────────────────────┘
                       │
          ┌────────────┼────────────┐
          │            │            │
     ┌────▼────┐  ┌───▼────┐  ┌───▼────┐
     │ Score   │  │Send to │  │ Render │
     │ vs JD   │  │ LLM    │  │  PDF   │
     │(TF-IDF/ │  │(strict │  │(Report │
     │ ONNX)   │  │prompt) │  │  Lab)  │
     └─────────┘  └────────┘  └────────┘
```

---

## Complete Pipeline Flow

### A. Document Upload Flow (one-time per document)

```
User uploads file (PDF/DOCX/TXT/MD)
  │
  ├─→ 1. Extract raw text
  │     ├─→ PDF: PyPDF2 or pdfplumber
  │     ├─→ DOCX: python-docx
  │     ├─→ TXT/MD: direct read
  │     └─→ Store original file in ~/.autoapply/uploads/
  │
  ├─→ 2. Send to cloud LLM with EXTRACTION_PROMPT
  │     └─→ "Parse this document into structured resume components:
  │          - Experience bullets (action verb + metric + context)
  │          - Skills (grouped by category)
  │          - Education entries
  │          - Project descriptions
  │          - Summary sentences
  │          - Certifications
  │          For each entry, tag with applicable job types:
  │          [backend, frontend, fullstack, data, devops, ml, management, ...]
  │          Output as JSON."
  │
  ├─→ 3. Parse LLM JSON response
  │     └─→ Validate structure, extract entries
  │
  └─→ 4. Insert into knowledge_base table
        ├─→ Deduplicate (UNIQUE constraint on category + text)
        ├─→ Auto-extract keyword tags
        ├─→ Compute ONNX embeddings (if available)
        └─→ Link to source document
```

### B. Resume Assembly Flow (per job application)

```
New JD arrives (passed score_job filter)
  │
  ├─→ 1. Score ALL KB entries against JD
  │     ├─→ ONNX embeddings (if available, precomputed)
  │     └─→ TF-IDF cosine similarity (always, fallback)
  │
  ├─→ 2. Select entries for resume (with limits)
  │     ├─→ Experience: top 15 entries
  │     ├─→ Skills: top 20 entries
  │     ├─→ Education: top 4 entries
  │     ├─→ Projects: top 6 entries
  │     ├─→ Certifications: top 5 entries
  │     └─→ Summary/contact/volunteer/awards: all matching
  │
  ├─→ 3. Check: enough content for a complete resume?
  │     ├─→ YES: Send selected entries to LLM with strict prompt
  │     │     ├─→ LLM returns markdown (1 page, min 2 bullets/role)
  │     │     ├─→ LLM may rephrase/use synonyms from JD, but ONLY uses provided data
  │     │     └─→ ReportLab renders markdown → PDF (Jake Gutierrez style)
  │     └─→ NO: Fall through to cloud LLM generation (legacy path)
  │
  └─→ 4. Record which KB entry IDs were used (not the PDF)
```

### C. Resume Viewing / Preview Flow (on demand)

```
User clicks "Preview Resume" from KB viewer
  │
  ├─→ Frontend sends POST /api/kb/preview
  ├─→ Backend: generate_resume_from_kb() selects entries via TF-IDF scoring
  ├─→ Backend: sends selected entries to LLM with strict "only use provided data" prompt
  ├─→ Backend: LLM returns markdown → render_resume_to_pdf() via ReportLab
  │     └─→ Jake Gutierrez style: 22pt centered name, 9.5pt body,
  │         11pt section headers with rules, two-column subheadings
  ├─→ Returns PDF blob to frontend
  └─→ Frontend displays in iframe/embed viewer
```

---

## New Files

| File | Purpose |
|------|---------|
| `core/document_parser.py` | Extract text from PDF/DOCX/TXT/MD uploads |
| `core/knowledge_base.py` | KnowledgeBase class: CRUD, query, migration, LLM extraction |
| `core/resume_scorer.py` | TF-IDF + ONNX embedding scoring algorithms |
| `core/resume_assembler.py` | Select KB entries, send to LLM, render PDF via ReportLab |
| `core/latex_compiler.py` | **DEPRECATED** — TinyTeX wrapper, not used in active pipeline |
| `templates/latex/*.tex.j2` | **DEPRECATED** — LaTeX templates exist on disk but template picker removed from UI. `jake.tex.j2` deleted in M4; remaining: classic, modern, academic, minimal |
| `electron/scripts/bundle-tinytex.js` | **DEPRECATED** — TinyTeX bundling no longer needed |
| `routes/knowledge_base.py` | API endpoints: upload, list, CRUD, import |
| `static/js/knowledge-base.js` | Frontend: upload UI, KB viewer, entry editor |
| `tests/test_document_parser.py` | ~8 tests: PDF/DOCX/TXT extraction |
| `tests/test_knowledge_base.py` | ~18 tests: CRUD, dedup, LLM extraction, migration |
| `tests/test_resume_scorer.py` | ~13 tests: TF-IDF, ONNX mock |
| `tests/test_resume_assembler.py` | ~12 tests: assembly, LLM prompt, ReportLab rendering |
| `tests/test_latex_compiler.py` | ~5 tests: binary detection, compilation |

## Modified Files

| File | Change |
|------|--------|
| `config/settings.py` | Add `ResumeReuseConfig`, `LatexConfig` (deprecated) models |
| `bot/bot.py` | Modify `_generate_docs()` — try KB assembly before LLM; ingest LLM output to KB |
| `core/ai_engine.py` | Add `EXTRACTION_PROMPT`, `extract_kb_entries()` function |
| `db/database.py` | Add `knowledge_base` + `uploaded_documents` tables; add `reuse_source`/`source_entry_ids` to `resume_versions` |
| `routes/resumes.py` | On-the-fly ReportLab rendering for PDF endpoint; never serve stored PDF for KB-assembled resumes |
| `routes/analytics.py` | Add `/api/analytics/reuse-stats` endpoint |
| `templates/index.html` | Upload UI, KB viewer section, reuse settings |
| `static/js/settings.js` | Load/save reuse config (LaTeX config removed from UI) |
| `static/locales/en.json` | ~25 new i18n keys |
| `static/locales/es.json` | ~25 new i18n keys (Spanish) |
| `pyproject.toml` | Add `jinja2`, `PyPDF2`, `python-docx`; optional `onnxruntime` + `tokenizers` |
| `electron/scripts/bundle-python.js` | ~~Add TinyTeX bundling step~~ (no longer needed) |
| `routes/config.py` | (M4) Add `POST/GET/DELETE /api/config/default-resume` endpoints for default resume upload |
| `config/settings.py` | (M4) Add `bot.cover_letter_enabled` to `BotConfig`; change `LatexConfig.template` default from "jake" to "classic" |
| `templates/index.html` | (M4) Dashboard automation toggles (Adaptive Resume, Cover Letter); default resume upload UI; KB page section reorder; preview popup with overlay |
| `static/js/settings.js` | (M4) `initBotToggles()`, `loadApplyMode()` toggle state loading, `uploadDefaultResume()`, `removeDefaultResume()`, `loadDefaultResume()` |
| `core/latex_compiler.py` | (M4) Remove "jake" from `AVAILABLE_TEMPLATES` |
| `tests/test_latex_compiler.py` | (M4) Update tests to use "classic" instead of "jake" |

---

## 1. Database Schema

### `uploaded_documents` — tracks raw uploads

```sql
CREATE TABLE uploaded_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    file_type TEXT NOT NULL,        -- 'pdf', 'docx', 'txt', 'md'
    file_path TEXT NOT NULL,        -- path in ~/.autoapply/uploads/
    raw_text TEXT,                  -- extracted plain text
    llm_provider TEXT,              -- which LLM processed it
    llm_model TEXT,
    processed_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### `knowledge_base` — the polished, categorized entries

```sql
CREATE TABLE knowledge_base (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    -- 'experience', 'skill', 'education', 'project', 'summary',
    -- 'certification', 'contact', 'volunteer', 'award'
    text TEXT NOT NULL,             -- the polished bullet/entry text
    subsection TEXT,                -- e.g. 'Senior Engineer — Acme Corp (2020-2023)'
    job_types TEXT,                 -- JSON: '["backend","fullstack","devops"]'
    tags TEXT,                      -- JSON: '["python","aws","microservices"]'
    source_doc_id INTEGER REFERENCES uploaded_documents(id),
    embedding BLOB,                -- ONNX 384-dim float32 vector, NULL if not computed
    is_active INTEGER NOT NULL DEFAULT 1,  -- user can soft-delete entries
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME,
    UNIQUE(category, text)         -- deduplication
);

CREATE INDEX idx_kb_category ON knowledge_base(category);
CREATE INDEX idx_kb_job_types ON knowledge_base(job_types);
CREATE INDEX idx_kb_active ON knowledge_base(is_active);
```

### `resume_versions` additions

```sql
ALTER TABLE resume_versions ADD COLUMN reuse_source TEXT;
-- 'llm_generated', 'kb_assembled', NULL (legacy)

ALTER TABLE resume_versions ADD COLUMN source_entry_ids TEXT;
-- JSON array: '[1, 5, 12, 34]' — which KB entries were used to build this resume
```

**Key design**: `resume_versions` stores `source_entry_ids` (a list of KB IDs), NOT a PDF path for KB-assembled resumes. The PDF is rendered on demand from these IDs.

---

## 2. LLM Extraction Prompt

```python
EXTRACTION_PROMPT = """
You are an expert career consultant. Parse this document into structured resume components.

For EACH item you extract, output it as a JSON object with these fields:
- "category": one of "experience", "skill", "education", "project", "summary", "certification", "award", "volunteer"
- "text": the polished, professional bullet point or entry. Use strong action verbs, quantify with metrics where present. Keep concise (1-2 lines max).
- "subsection": the role/company/institution context (e.g., "Senior Engineer — Acme Corp (2020-2023)"). Null for skills/certs.
- "job_types": array of job categories this entry is relevant to. Choose from: ["backend", "frontend", "fullstack", "data_engineer", "data_scientist", "devops", "cloud", "ml_engineer", "mobile", "security", "management", "product", "qa", "embedded", "general"]

Rules:
- Extract EVERY distinct achievement, skill, education entry, project, and certification
- Make bullet points professional and ATS-optimized: "Verb + What + Metric + Context"
- Do NOT invent metrics or facts not present in the source
- DO improve grammar, tense consistency, and professional tone
- Group related skills (e.g., "Python, Flask, Django" as one skill entry for "backend")
- For experience bullets, preserve the original company/role as subsection context
- Create 2-3 summary sentences that capture the person's overall profile, tagged by job type

Output ONLY a JSON array of objects. No preamble, no explanation.

---
DOCUMENT CONTENT:
{document_text}
"""
```

This prompt is called **once per upload**, not per job application.

---

## 3. Config Schema

```python
class ResumeReuseConfig(BaseModel):
    enabled: bool = True
    min_score: float = 0.60             # minimum score for a KB entry to be included
    min_experience_bullets: int = 6     # need at least N experience entries above min_score
    scoring_method: str = "auto"        # "tfidf" | "onnx" | "auto"
    cover_letter_strategy: str = "generate"  # "generate" | "template"

class LatexConfig(BaseModel):
    template: str = "default"           # template name in templates/latex/
    font_family: str = "helvetica"      # helvetica, times, palatino
    font_size: int = 11                 # 10, 11, 12
    margin: str = "0.75in"
```

---

## 4. Document Parser (`core/document_parser.py`)

```python
def extract_text(file_path: Path) -> str:
    """Extract plain text from uploaded document."""
    ext = file_path.suffix.lower()
    if ext == ".pdf":
        return _extract_from_pdf(file_path)    # PyPDF2 or pdfplumber
    elif ext in (".docx", ".doc"):
        return _extract_from_docx(file_path)   # python-docx
    elif ext in (".txt", ".md"):
        return file_path.read_text(encoding="utf-8")
    else:
        raise ValueError(f"Unsupported file type: {ext}")
```

---

## 5. Knowledge Base Class (`core/knowledge_base.py`)

```python
class KnowledgeBase:
    def __init__(self, db: Database):
        self.db = db

    def process_upload(self, file_path: Path, llm_config) -> int:
        """Full pipeline: extract text → LLM → insert entries. Returns count inserted."""
        raw_text = extract_text(file_path)
        doc_id = self.db.save_uploaded_document(file_path, raw_text)
        entries = self._extract_via_llm(raw_text, llm_config)
        inserted = self._insert_entries(entries, doc_id)
        return inserted

    def _extract_via_llm(self, text: str, llm_config) -> list[dict]:
        """Call cloud LLM to extract structured entries from raw text."""
        prompt = EXTRACTION_PROMPT.format(document_text=text[:8000])
        response = invoke_llm(prompt, llm_config)
        return json.loads(response)  # validate JSON array

    def _insert_entries(self, entries: list[dict], doc_id: int) -> int:
        """Insert entries into KB, deduplicating. Returns count inserted."""
        ...

    def score_against_jd(self, jd_text: str, scoring_method: str = "auto") -> list[ScoredEntry]:
        """Score all active KB entries against a JD. Returns sorted by score descending."""
        ...

    def get_entries_by_ids(self, ids: list[int]) -> list[dict]:
        """Fetch specific entries for resume rendering."""
        ...
```

---

## 6. Resume Assembler (`core/resume_assembler.py`)

```python
def assemble_resume(
    jd_text: str,
    kb: KnowledgeBase,
    profile: UserProfile,
    reuse_config: ResumeReuseConfig,
    llm_config: LLMConfig,
) -> AssemblyResult | None:
    """Score KB, select entries, send to LLM, render PDF via ReportLab.
    Returns None if not enough content."""

    # 1. Score all active KB entries against JD
    scored = kb.score_against_jd(jd_text, reuse_config.scoring_method)

    # 2. Filter by min_score
    above_threshold = [s for s in scored if s.score >= reuse_config.min_score]

    # 3. Select entries per category (with limits)
    selected = _select_entries(above_threshold, reuse_config)
    # Limits: experience=15, skill=20, education=4, project=6, certification=5

    # 4. Check completeness
    experience_count = sum(1 for s in selected if s.category == "experience")
    if experience_count < reuse_config.min_experience_bullets:
        return None  # not enough content, fall through to LLM

    # 5. Send selected entries to LLM with strict prompt
    #    - "Only use provided data — no hallucinated experiences"
    #    - "Exactly 1 page, minimum 2 bullets per role"
    #    - "May rephrase and use synonyms from JD"
    markdown_resume = generate_resume_from_kb(selected, jd_text, llm_config)

    # 6. Render markdown to PDF via ReportLab (Jake Gutierrez style)
    pdf_bytes = render_resume_to_pdf(markdown_resume)

    # 7. Return result with entry IDs for storage
    return AssemblyResult(
        pdf_bytes=pdf_bytes,
        source_entry_ids=[s.id for s in selected],
        avg_score=mean(s.score for s in selected),
    )
```

---

## 7. Bot Loop Integration

```python
# bot/bot.py:_generate_docs() — modified

def _generate_docs(scored, config, profile_dir):
    from core.knowledge_base import KnowledgeBase
    from core.resume_assembler import assemble_resume

    # --- Try KB assembly first ---
    if config.resume_reuse.enabled:
        kb = KnowledgeBase(db)
        result = assemble_resume(
            jd_text=scored.raw.description,
            kb=kb,
            profile=config.profile,
            reuse_config=config.resume_reuse,
            llm_config=config.llm,
        )
        if result:
            logger.info("KB assembly: score=%.2f, %d entries used",
                        result.avg_score, len(result.source_entry_ids))
            cl_path, cl_text = _handle_cover_letter(scored, config, profile_dir)
            version_meta = {
                "resume_pdf_path": str(result.pdf_path),
                "llm_provider": "local_kb",
                "llm_model": "kb_assembled",
                "reuse_source": "kb_assembled",
                "source_entry_ids": json.dumps(result.source_entry_ids),
            }
            return result.pdf_path, cl_path, cl_text, version_meta

    # --- Existing LLM generation path ---
    try:
        resume_path, cl_path, version_meta = generate_documents(...)
        # NEW: Ingest the LLM-generated resume into KB for future reuse
        kb.ingest_generated_resume(resume_path, version_meta)
        ...
```

---

## 8. Resume Viewing (On-Demand Rendering)

```python
# routes/resumes.py — modified PDF endpoint

@bp.route("/api/resumes/<int:vid>/pdf")
def serve_resume_pdf(vid):
    version = db.get_resume_version(vid)

    if version.get("reuse_source") == "kb_assembled":
        # Render on-the-fly from KB entry IDs via LLM + ReportLab
        entry_ids = json.loads(version["source_entry_ids"])
        entries = kb.get_entries_by_ids(entry_ids)
        markdown = generate_resume_from_kb(entries, jd_text, llm_config)
        pdf_bytes = render_resume_to_pdf(markdown)  # ReportLab
        return Response(pdf_bytes, mimetype="application/pdf")
    else:
        # Legacy: serve stored PDF file
        return send_file(version["resume_pdf_path"])
```

**Preview endpoint** (current implementation):

```
POST /api/kb/preview
  Body: { jd_text: str | null }
  Backend:
    1. generate_resume_from_kb() — TF-IDF scoring → LLM with strict prompt
    2. render_resume_to_pdf() — ReportLab renderer (Jake Gutierrez style)
  Response:
    Content-Type: application/pdf (binary blob)
```

---

## 9. Upload API Endpoints (`routes/knowledge_base.py`)

```
POST   /api/kb/upload          — Upload document, trigger LLM extraction
GET    /api/kb/entries          — List all KB entries (paginated, filterable)
GET    /api/kb/entries/<id>     — Get single entry
PUT    /api/kb/entries/<id>     — Edit entry text/tags/job_types
DELETE /api/kb/entries/<id>     — Soft-delete (set is_active=0)
POST   /api/kb/entries          — Manually add an entry
GET    /api/kb/documents        — List uploaded documents
DELETE /api/kb/documents/<id>   — Delete document + its entries
GET    /api/kb/stats            — Entry counts by category, source, job type
POST   /api/kb/reprocess/<doc_id> — Re-run LLM extraction on a document
```

---

## 10. Frontend UI

### Upload Section (prominent, in profile/settings area)
- Drag-and-drop zone for PDF/DOCX/TXT/MD files
- "Upload" button with file picker
- Progress indicator during LLM extraction
- Success message: "Extracted N entries from your document"
- Encourage: "Upload resumes, project descriptions, LinkedIn exports — the more, the better!"

### Knowledge Base Viewer (new tab in main nav)
- Table: category icon, entry text (truncated), subsection, job types badges, tags, source doc, date
- Filter bar: category dropdown, job type dropdown, search text
- Inline edit: click entry text to edit directly
- Bulk actions: delete selected, re-tag selected
- Stats cards: total entries, by category breakdown, by job type
- "Add Entry" button for manual entry

### Settings Section
- Toggle: Enable Smart Resume Assembly
- Slider/number: Min score threshold (0.0-1.0)
- Number: Min experience bullets
- Dropdown: Scoring method (Auto / TF-IDF Only)
- ~~Collapsible "LaTeX": template, font, size, margin~~ (removed — no template picker in UI)

---

## 11. ~~LaTeX Template Gallery + Live Preview~~ DEPRECATED

> **DEPRECATED**: The LaTeX template gallery and live preview with template picker have been
> replaced by the LLM + ReportLab pipeline. The ReportLab renderer uses a single fixed style
> matching the Jake Gutierrez resume template (22pt centered name, 9.5pt body, 11pt section
> headers with rules, two-column subheadings). Template files still exist on disk in
> `templates/latex/` but are not used in the active pipeline. `loadTemplates()` has been
> removed from JS initialization. The template picker UI has been removed from `index.html`.
>
> The preview endpoint is now `POST /api/kb/preview` which calls `generate_resume_from_kb()`
> then `render_resume_to_pdf()` and returns a PDF blob directly.

### Template System (DEPRECATED — retained for reference)

Users can choose from multiple resume styles. Each template is a `.tex.j2` file in `templates/latex/` that receives the same data context (entries, profile, config) but renders differently.

#### Bundled Templates

| Template | File | Style | Best For |
|----------|------|-------|----------|
| **Classic** (default) | `resume_classic.tex.j2` | Clean single-column, Helvetica, thin section rules | General/corporate roles |
| **Modern** | `resume_modern.tex.j2` | Sans-serif, subtle color accents (dark blue headers), compact spacing | Tech/startup roles |
| **Academic** | `resume_academic.tex.j2` | Times/Palatino, generous margins, publications section | Research/academic roles |
| **Minimal** | `resume_minimal.tex.j2` | Ultra-clean, no rules, extra whitespace, lightweight | Design/creative-adjacent |

All templates are **ATS-safe**: no tables, no multi-column, no images, standard fonts, proper heading hierarchy.

#### Template Data Context (passed to all templates via Jinja2)

```python
{
    "name": "Jane Smith",
    "contact_line": "jane@example.com | 555-1234 | San Francisco, CA | linkedin.com/in/jane",
    "summary": "Experienced backend engineer with 8 years...",
    "experience_sections": [
        {
            "heading": "Senior Engineer — Acme Corp (2020 - Present)",
            "bullets": ["Led migration to microservices...", "Managed team of 5..."]
        },
        ...
    ],
    "skills": "Python, Flask, Django, PostgreSQL, AWS, Docker",
    "education_entries": ["BS Computer Science — MIT (2016)"],
    "certifications": ["AWS Solutions Architect Associate (2023)"],
    "projects": [
        {
            "heading": "Open Source Contributor — FastAPI",
            "bullets": ["Implemented OAuth2 scopes middleware..."]
        }
    ],
    # LaTeX config
    "font_family": "helvetica",
    "font_size": 11,
    "margin": "0.75in",
}
```

#### Custom Templates (Future)

Users can drop their own `.tex.j2` files into `~/.autoapply/templates/` and they appear in the template picker. The app validates that the template compiles before allowing selection.

### Live Preview

#### How It Works

```
User opens "Resume Preview" (from KB viewer, settings, or application detail)
  │
  ├─→ Frontend sends POST /api/resumes/preview
  │     Body: { template: "modern", entry_ids: [1,5,12,34], latex_config: {...} }
  │     OR: { template: "modern", jd_text: "...", auto_select: true }
  │
  ├─→ Backend:
  │     1. Fetch KB entries (by IDs or auto-select against JD)
  │     2. Render Jinja2 template with entries + profile
  │     3. Compile LaTeX → ephemeral PDF
  │     4. Return PDF as binary response
  │
  └─→ Frontend:
        1. Display PDF in iframe/embed viewer
        2. Template picker sidebar: click different template → re-request preview
        3. Entry toggle: checkbox each KB entry → re-request with updated IDs
```

#### Preview API (DEPRECATED — replaced by POST /api/kb/preview)

```
# DEPRECATED — was:
POST /api/resumes/preview    (LaTeX template picker + entry toggle)
GET  /api/resumes/templates  (template list with thumbnails)

# CURRENT:
POST /api/kb/preview
  Body:
    jd_text: str | null     — optional JD for scoring-based entry selection
  Response:
    Content-Type: application/pdf
    (binary PDF blob from LLM markdown → ReportLab)
```

#### Preview UI (Frontend)

```
┌─────────────────────────────────────────────────────────────────┐
│  Resume Preview                                          [✕]    │
├────────────────────┬────────────────────────────────────────────┤
│                    │                                            │
│  TEMPLATE          │                                            │
│  ┌──────────────┐  │                                            │
│  │ ● Classic    │  │         ┌─────────────────────┐            │
│  │ ○ Modern     │  │         │                     │            │
│  │ ○ Academic   │  │         │   PDF PREVIEW        │            │
│  │ ○ Minimal    │  │         │   (iframe/embed)     │            │
│  └──────────────┘  │         │                     │            │
│                    │         │   Jane Smith         │            │
│  FONT              │         │   jane@example.com   │            │
│  [Helvetica ▾]     │         │                     │            │
│                    │         │   Summary            │            │
│  SIZE  [11 ▾]      │         │   ─────────────────  │            │
│                    │         │   Experienced...     │            │
│  ──────────────    │         │                     │            │
│                    │         │   Experience         │            │
│  INCLUDED ENTRIES  │         │   ─────────────────  │            │
│  ☑ Led migration.. │         │   ...               │            │
│  ☑ Managed team..  │         │                     │            │
│  ☐ Built REST API  │         └─────────────────────┘            │
│  ☑ Python, Flask.. │                                            │
│  ☑ BS CompSci..    │         [Download PDF]  [Use for Job]      │
│                    │                                            │
└────────────────────┴────────────────────────────────────────────┘
```

**Interactions:**
- Click template → re-renders preview with new template (debounced, 500ms)
- Toggle entry checkbox → re-renders with updated entry list
- Change font/size → re-renders
- "Download PDF" → downloads the currently previewed PDF
- "Use for Job" → saves the current entry IDs + template as the resume for an application

#### Preview from Multiple Entry Points

1. **Knowledge Base tab** → "Preview Resume" button → opens preview with all active entries
2. **Application detail** → "View Resume" → opens preview with stored entry IDs
3. **Bot review mode** → before approving application, preview the assembled resume
4. **Settings** → "Preview with sample data" → shows template styles with dummy content

#### Template Thumbnails

Static PNG thumbnails (`static/img/tpl-*.png`) generated once from sample data. Shown in template picker for quick visual comparison without compiling LaTeX.

---

## 12. Scoring Algorithms

### Tier 1: TF-IDF (stdlib, always available)
- Hand-rolled: `collections.Counter`, `math`, `re`
- <30ms for 200 entries

### Tier 2: ONNX Embeddings (optional, ~130MB)
- `onnxruntime` + `tokenizers` (no PyTorch)
- all-MiniLM-L6-v2 ONNX (~80MB), 384-dim vectors
- Precomputed embeddings in `knowledge_base.embedding` column
- ~50ms for 200 entries (precomputed)

### Blending
```
auto mode: 0.3 * tfidf + 0.7 * onnx (if available), else tfidf only
```

---

## 13. Auto-Migration (Backward Compatibility)

On first run after upgrade:
1. Scan `~/.autoapply/profile/experiences/*.txt` — treat as document uploads, run through extraction pipeline
2. Scan `~/.autoapply/profile/resumes/*.md` — parse existing LLM-generated resumes into KB entries
3. Existing `resume_versions` with `reuse_source=NULL` → legacy, continue serving stored PDFs
4. New `resume_versions` with `reuse_source='kb_assembled'` → render from entry IDs

---

## 14. Cover Letter Strategy

| Strategy | API Calls | Notes |
|----------|-----------|-------|
| `"generate"` (default) | 1 | LLM generates fresh cover letter per job |
| `"template"` | 0 | Uses `config.bot.cover_letter_template` |

---

## 15. Implementation Phases (10 Milestones)

Each milestone is a standalone PR with tests, i18n, and production-readiness built in.

### Milestone 1: Foundation — KB + Roles + Document Parser + DB
**Scope**: Core data layer + text extraction. No UI, no scoring, no LaTeX.
1. `db/database.py` — `knowledge_base`, `roles`, `uploaded_documents` tables + migrations
2. `core/document_parser.py` — PDF/DOCX/TXT/MD text extraction (PyPDF2, python-docx, raw read)
3. `core/knowledge_base.py` — KnowledgeBase class: CRUD, dedup, LLM extraction call
4. `core/resume_parser.py` — Parse .md resumes into KB entries (for migration + LLM output ingestion)
5. `core/experience_calculator.py` — Domain-specific years calculation from roles table
6. `core/ai_engine.py` — Add `EXTRACTION_PROMPT` + `extract_kb_entries()` function
7. `config/settings.py` — `ResumeReuseConfig` + `LatexConfig` Pydantic models
8. Tests: ~35 tests (document parsing, KB CRUD, dedup, resume parsing, experience calc)

### Milestone 2: Scoring Engine — TF-IDF + JD Analyzer
**Scope**: Score KB entries against job descriptions. No assembly, no LaTeX.
1. `core/resume_scorer.py` — Hand-rolled TF-IDF cosine similarity (stdlib only)
2. `core/jd_analyzer.py` — Keyword extraction (tech dictionary, n-grams, synonym normalization, section detection)
3. ONNX embedding support (optional, with mocked tests)
4. Score blending: 0.3*TF-IDF + 0.7*ONNX (when available), pure TF-IDF fallback
5. Tests: ~15 tests (TF-IDF scoring, keyword extraction, ONNX mock, blending)

### Milestone 3: LaTeX Engine — Templates + Compiler — DEPRECATED
> **DEPRECATED**: M3 was completed but the LaTeX pipeline has been superseded by the
> LLM + ReportLab pipeline in M4. The LaTeX compiler code (`core/latex_compiler.py`)
> and templates (`templates/latex/*.tex.j2`) still exist on disk but are not used in
> the active resume generation flow. TinyTeX bundling is no longer required for
> distribution. Tests in `tests/test_latex_compiler.py` still pass but cover
> deprecated functionality.

**Scope**: ~~LaTeX template rendering + PDF compilation.~~ (superseded by LLM + ReportLab)
1. `core/latex_compiler.py` — Find pdflatex (bundled TinyTeX → system PATH), compile .tex → .pdf
2. `templates/latex/` — 4 Jinja2 LaTeX templates: classic, modern, academic, minimal
3. `electron/scripts/bundle-tinytex.js` — Download + bundle TinyTeX per platform
4. Template thumbnail PNG generation for picker UI
5. `pyproject.toml` — Add `jinja2` dependency
6. Tests: ~8 tests (binary detection, compilation, error handling, template rendering)

### Milestone 4: Resume Assembly + Bot Integration
**Scope**: Connect scoring + LLM + ReportLab + bot loop. The core "smart reuse" flow.
1. `core/resume_assembler.py` — Score KB → select entries (experience=15, skill=20, education=4, project=6, certification=5) → send to LLM with strict "only use provided data" prompt → LLM returns markdown → ReportLab renders PDF
2. `bot/bot.py` — Modify `_generate_docs()`: try KB assembly first, fall through to LLM
3. `core/ai_engine.py` — Post-generation ingestion: parse LLM output → insert into KB
4. `db/database.py` — Add `reuse_source`, `source_entry_ids` columns to `resume_versions`
5. `routes/knowledge_base.py` — `POST /api/kb/preview` endpoint: `generate_resume_from_kb()` → `render_resume_to_pdf()` → returns PDF blob
6. ReportLab renderer: Jake Gutierrez style (22pt centered name, 9.5pt body, 11pt section headers with rules, two-column subheadings)
7. `assemble_resume()` takes `llm_config` (not `latex_config`) — LLM generates exactly 1 page, min 2 bullets per role, may rephrase/use synonyms from JD
8. Frontend: `loadTemplates()` removed from JS initialization, `loadKBDocuments()` added, Resume Templates section removed from UI
9. Tests: ~15 tests (assembly, bot integration, preview endpoint, ReportLab rendering)
10. **Dashboard Automation Toggles**: "Adaptive Resume" and "Cover Letter" checkboxes added to Dashboard bot control card. Auto-save on toggle via `PUT /api/config` (no Save button). `initBotToggles()` in `settings.js` binds change events; `loadApplyMode()` extended to load toggle states. `bot.cover_letter_enabled` config field added to `BotConfig`. When Cover Letter off: `generate_documents(skip_cover_letter=True)` skips LLM call. When Adaptive Resume off: `_try_kb_assembly()` returns `None`, bot uses fallback.
11. **Default Resume Upload**: 3 new endpoints in `routes/config.py`: `POST/GET/DELETE /api/config/default-resume`. Accepts PDF/DOCX up to 5 MB, saves to `~/.autoapply/default_resume.{ext}`. Updates `config.profile.fallback_resume_path`. Dashboard UI: filename display + Upload button + Remove (X) button. `uploadDefaultResume()`, `removeDefaultResume()`, `loadDefaultResume()` in `settings.js`.
12. **KB Page UI Restructure**: Reordered sections: Stats → ATS + Smart Resume Assembly → Resume Builder + Documents → KB Entries. Upload control moved inside "Uploaded Documents" card. Resume Templates section removed (LaTeX deprecated). Preview popup: fixed overlay, z-index 1000, dark bg, Close + Download buttons.
13. **Jake Template Removal**: Deleted `templates/latex/jake.tex.j2`. Removed "jake" from `AVAILABLE_TEMPLATES` in `latex_compiler.py`. Changed `LatexConfig.template` default from "jake" to "classic". Updated tests to use "classic" instead of "jake".

### Milestone 5: Upload UI + KB Viewer + Preview
**Scope**: Frontend for document upload, KB browsing, and resume preview.
1. `routes/knowledge_base.py` — Blueprint: upload, CRUD, search endpoints
2. `static/js/knowledge-base.js` — Upload zone + KB table viewer (filter, search, edit, delete) + `loadKBDocuments()` on init
3. `static/js/resume-preview.js` — Preview modal: PDF render via `POST /api/kb/preview` (no template picker)
4. `templates/index.html` — Upload zone section, KB tab, settings section, preview modal (no template picker)
5. `static/js/settings.js` — Reuse config only (LaTeX config and template selector removed)
6. `static/locales/en.json` + `es.json` — ~30 new i18n keys
7. ARIA labels, keyboard navigation, focus management on all new UI
8. Tests: ~12 tests (upload API, CRUD endpoints, preview endpoint)

### Milestone 6: ATS Scoring + Platform Profiles
**Scope**: Platform-specific resume optimization for ATS systems.
1. `core/ats_scorer.py` — Composite ATS score (required keywords 35%, preferred 15%, experience 25%, title 15%, qualifications 10%)
2. `core/ats_profiles.py` — Platform-specific profiles (Workday, Greenhouse, Lever, LinkedIn, Indeed, Ashby)
3. ATS score display in resume preview + application tracker
4. Keyword gap analysis: show missing required/preferred keywords
5. Tests: ~10 tests (scoring, profiles, gap analysis)

### Milestone 7: Manual Resume Builder
**Scope**: Drag-and-drop resume creation from KB entries.
1. `static/js/resume-builder.js` — Drag-and-drop interface for KB entry selection
2. Resume presets: save/load named entry ID combinations
3. `routes/knowledge_base.py` — Preset CRUD endpoints
4. `db/database.py` — `resume_presets` table
5. One-page mode: line estimation + post-compile page count validation
6. Tests: ~8 tests (presets, one-page validation)

### Milestone 8: Performance + Intelligence
**Scope**: Caching, batch scoring, smart optimizations.
1. PDF compilation cache (content-hash based, LRU eviction)
2. Precomputed embedding index + incremental updates
3. Job-type pre-filtering for scoring (reduce candidate set)
4. Batch job scoring (matrix multiply for multiple JDs)
5. Async document processing (background thread + SocketIO progress)
6. Tests: ~10 tests (caching, batch scoring, async processing)

### Milestone 9: User Intelligence Features
**Scope**: Learning + analytics for continuous improvement.
1. Outcome-based learning: `effectiveness_score` adjusted from interview/rejection outcomes
2. Cover letter KB: extract paragraphs, assemble locally (0 API calls)
3. JD classifier: keyword-based job type detection for pre-filtering
4. `routes/analytics.py` — Reuse stats endpoint (API calls saved, cost savings)
5. Tests: ~8 tests (learning, CL assembly, classification)

### Milestone 10: Migration + Polish + Extras
**Scope**: Auto-migration, edge cases, final quality pass.
1. Auto-migration of existing `~/.autoapply/profile/experiences/*.txt` and `resumes/*.md`
2. Edge cases: LaTeX special character escaping, empty KB handling, large file uploads
3. Error handling: upload failures, compilation errors, malformed documents
4. Full test suite verification (all 900+ tests pass)
5. `CHANGELOG.md` update, documentation

---

## 16. Graceful Degradation

| Scenario | Behavior |
|----------|----------|
| Empty knowledge base | Falls through to LLM generation |
| LLM extraction fails on upload | Store raw text, retry later, show error to user |
| pdflatex not found | N/A — ReportLab is the primary renderer (no LaTeX dependency) |
| ReportLab rendering error | Returns error to user with details; no silent failure |
| Not enough matching entries | Falls through to LLM generation |
| ONNX not installed | TF-IDF only |
| Uploaded file unreadable | Show error, don't crash |

**ReportLab is the primary renderer** — `render_resume_to_pdf()` is the sole PDF generation path. LaTeX compiler code exists but is deprecated.

---

## 17. Distribution Impact

| Component | Size | Required? |
|-----------|------|-----------|
| ~~TinyTeX bundle~~ | ~~100 MB~~ | No longer bundled (LaTeX deprecated) |
| ReportLab | ~3 MB | Required (primary PDF renderer) |
| Jinja2 | ~1 MB | Required |
| PyPDF2 | ~1 MB | Required |
| python-docx | ~2 MB | Required |
| TF-IDF (stdlib) | 0 MB | Always |
| `onnxruntime` | ~50 MB | Optional |
| `tokenizers` | ~5 MB | Optional |
| MiniLM ONNX model | ~80 MB | Auto-download |

**Default bundle**: ~455-505 MB (~100 MB less than original plan — no TinyTeX).
**With ONNX**: additional ~135 MB user-downloaded.

---

## 18. Verification

1. Unit tests: `pytest tests/test_document_parser.py tests/test_knowledge_base.py tests/test_resume_scorer.py tests/test_resume_assembler.py tests/test_latex_compiler.py -v`
2. Full suite: `pytest tests/ -v` (all 817+ existing tests pass)
3. Lint: `ruff check .`
4. Manual: upload a PDF resume, verify KB populated with entries
5. Manual: upload a .txt experience file, verify extraction
6. Manual: run bot with similar JD, verify KB assembly triggers
7. Manual: click "Preview Resume" from KB viewer, verify PDF rendered via ReportLab
8. Manual: disable reuse, verify LLM generation still works + ingests to KB
9. Manual: verify ReportLab PDF matches Jake Gutierrez style (22pt name, 9.5pt body, section rules)

---

## 19. Performance & Efficiency Optimizations

### 19.1 PDF Rendering Cache

LLM generation is the heaviest operation (~2-5s per call). Cache rendered PDFs by content hash of the LLM markdown output.

```python
# core/resume_assembler.py
import hashlib

PDF_CACHE_DIR = Path("~/.autoapply/cache/pdf/").expanduser()

def render_cached(markdown_content: str) -> bytes:
    """Render markdown to PDF with content-hash caching. Returns cached PDF if available."""
    content_hash = hashlib.sha256(markdown_content.encode()).hexdigest()[:16]
    cached_pdf = PDF_CACHE_DIR / f"{content_hash}.pdf"
    if cached_pdf.exists():
        logger.debug("PDF cache hit: %s", content_hash)
        return cached_pdf.read_bytes()
    pdf_bytes = render_resume_to_pdf(markdown_content)
    cached_pdf.write_bytes(pdf_bytes)
    return pdf_bytes
```

**Cache invalidation**: Same LLM markdown output = same hash → cache hit. Different JD or different KB entries produce different LLM output, busting the cache naturally.

**Cache cleanup**: LRU eviction — keep last 200 PDFs (~100MB), delete oldest on overflow. Run cleanup on app startup.

**Impact**: ReportLab rendering is already fast (~50ms), but caching avoids redundant LLM calls when the same resume is previewed multiple times.

### 19.2 Precomputed Embedding Index

Instead of scoring every KB entry on every job, precompute and index embeddings.

```python
# On KB entry insert/update:
embedding = onnx_encode(entry.text)  # 384-dim vector
db.update_entry_embedding(entry.id, embedding)

# On scoring:
jd_embedding = onnx_encode(jd_text)
# Fetch all embeddings in one query (they're in the DB as BLOBs)
# Compute cosine similarity as numpy dot product — vectorized, ~5ms for 500 entries
scores = np.dot(all_embeddings, jd_embedding) / (norms * jd_norm)
```

**Impact**: Scoring 500 KB entries drops from ~100ms (individual encode each) to **~5ms** (single JD encode + vectorized dot product).

### 19.3 Job-Type Pre-Filtering

Before scoring, filter KB entries by `job_types` tag to reduce the scoring set.

```python
def score_against_jd(self, jd_text: str, job_type_hint: str = None):
    # 1. Classify JD into job type (simple keyword match or LLM tag)
    detected_type = classify_jd(jd_text)  # "backend", "frontend", etc.

    # 2. Filter KB to entries matching that job type
    candidates = self.db.get_entries_by_job_type(detected_type)
    # Fallback: if < min_bullets, expand to "general" + related types

    # 3. Score only the filtered set
    return self._score_entries(candidates, jd_text)
```

**JD classifier** — lightweight, no LLM needed:
```python
JOB_TYPE_KEYWORDS = {
    "backend": ["api", "server", "database", "flask", "django", "node", "microservices"],
    "frontend": ["react", "vue", "angular", "css", "ui", "ux", "component"],
    "data_engineer": ["pipeline", "etl", "spark", "airflow", "warehouse"],
    "devops": ["ci/cd", "kubernetes", "docker", "terraform", "aws", "infrastructure"],
    "ml_engineer": ["model", "training", "tensorflow", "pytorch", "inference"],
    ...
}
def classify_jd(jd_text: str) -> str:
    jd_lower = jd_text.lower()
    scores = {jtype: sum(1 for kw in kws if kw in jd_lower) for jtype, kws in JOB_TYPE_KEYWORDS.items()}
    return max(scores, key=scores.get) if max(scores.values()) > 0 else "general"
```

**Impact**: If user has 500 KB entries across 5 job types, scoring only processes ~100 relevant entries instead of 500. **5x speedup** on scoring.

### 19.4 Smart Page-Length Optimization

A resume that's too short (half page) or too long (2 pages) hurts. The LLM prompt explicitly requires exactly 1 page, and the assembler enforces selection limits.

```python
def _select_entries(scored_entries, reuse_config):
    """Select entries within category limits for 1-page resume."""
    # Category limits enforce content volume:
    #   - Experience: max 15 entries
    #   - Skills: max 20 entries
    #   - Education: max 4 entries
    #   - Projects: max 6 entries
    #   - Certifications: max 5 entries
    #
    # LLM prompt requires exactly 1 page, min 2 bullets per role
    MAX_LINES = 48  # conservative target (used for estimation only)

    selected = []
    line_count = 0

    # Always include: contact (2 lines) + summary (3 lines) + education + skills
    line_count += 2 + 3 + estimate_lines(education) + estimate_lines(skills)

    # Fill remaining space with top-scored experience bullets
    for entry in sorted_experience_entries:
        bullet_lines = estimate_lines(entry.text)
        if line_count + bullet_lines <= MAX_LINES:
            selected.append(entry)
            line_count += bullet_lines
        else:
            break  # page is full

    # Add projects only if space remains
    ...
```

**Impact**: Every assembled resume fits on exactly one page — professional and ATS-optimal.

### 19.5 ATS Keyword Gap Analysis

After assembling a resume, compare it against the JD to identify missing keywords that the user's KB doesn't cover.

```python
def analyze_keyword_gaps(jd_text: str, selected_entries: list) -> list[str]:
    """Find important JD keywords not covered by selected entries."""
    jd_keywords = extract_important_keywords(jd_text)  # TF-IDF top terms
    resume_keywords = set()
    for entry in selected_entries:
        resume_keywords.update(tokenize(entry.text))

    missing = [kw for kw in jd_keywords if kw not in resume_keywords]
    return missing[:10]  # top 10 gaps
```

**Surfaced to user**:
- In preview modal: "Missing keywords: Kubernetes, Terraform, GraphQL"
- In bot review mode: "This resume may miss ATS keywords: [list]"
- Encourages user to upload more documents or add manual KB entries

**Impact**: Helps user improve their KB over time. Transparent about resume quality.

### 19.6 Outcome-Based Learning (Feedback Loop)

Track which KB entries appear in resumes that get interviews vs. rejections.

```sql
-- When user marks application status as "interview" or "rejected":
-- Update a score multiplier on each KB entry used in that resume

ALTER TABLE knowledge_base ADD COLUMN effectiveness_score FLOAT DEFAULT 1.0;
-- > 1.0 = entries that lead to interviews more often
-- < 1.0 = entries that appear in rejected applications
```

```python
def update_effectiveness(entry_ids: list[int], got_interview: bool):
    """Adjust effectiveness scores based on application outcome."""
    multiplier = 1.05 if got_interview else 0.98  # small adjustments
    for eid in entry_ids:
        db.execute(
            "UPDATE knowledge_base SET effectiveness_score = "
            "MIN(2.0, MAX(0.5, effectiveness_score * ?)) WHERE id = ?",
            (multiplier, eid)
        )

# In scoring, blend with effectiveness:
final_score = similarity_score * entry.effectiveness_score
```

**Impact**: Over time, the system learns which bullets lead to interviews and prioritizes them. Self-improving without any LLM calls.

### 19.7 Async Document Processing

Don't block the user during LLM extraction on upload. Process in background.

```python
# routes/knowledge_base.py
@bp.route("/api/kb/upload", methods=["POST"])
def upload_document():
    file = request.files["file"]
    # Save file immediately
    doc_id = save_uploaded_document(file)
    # Queue extraction in background thread
    threading.Thread(target=_process_upload, args=(doc_id, llm_config), daemon=True).start()
    return jsonify({"doc_id": doc_id, "status": "processing"})

# Frontend polls: GET /api/kb/documents/<id> → status: "processing" | "complete" | "error"
# Or use SocketIO emit when done
```

**Impact**: Upload returns instantly. User sees "Processing..." badge on the document. SocketIO event fires when extraction completes, UI updates live.

### 19.8 Batch Job Scoring

When the bot finds 20 jobs in one search cycle, don't score KB entries 20 times independently. Score once, rank for all jobs.

```python
def score_batch(jd_texts: list[str], kb_entries: list) -> dict[int, list[ScoredEntry]]:
    """Score KB entries against multiple JDs efficiently."""
    # 1. Encode all JDs at once (ONNX batch encode)
    jd_embeddings = onnx_batch_encode(jd_texts)

    # 2. KB embeddings already precomputed in DB
    kb_embeddings = load_all_embeddings()

    # 3. Matrix multiply: (n_jds x 384) @ (384 x n_entries) = (n_jds x n_entries)
    scores_matrix = np.dot(jd_embeddings, kb_embeddings.T)

    # 4. Return per-JD sorted scores
    return {i: sorted_scores for i, sorted_scores in enumerate(scores_matrix)}
```

**Impact**: Scoring 20 JDs against 500 entries: from 20 × 100ms = **2s** → single matrix multiply = **~15ms**.

### 19.9 Cover Letter Knowledge Base

Apply the same KB concept to cover letters. Extract "cover letter paragraphs" from uploads:
- Opening paragraphs (company-specific hooks)
- Body paragraphs (experience narratives)
- Closing paragraphs (call to action)

Tag each with job type. Assemble cover letters the same way as resumes — no LLM per application.

```python
# In EXTRACTION_PROMPT, add:
# - "cover_opening": compelling first paragraph templates
# - "cover_body": narrative paragraphs linking experience to value
# - "cover_closing": professional closing paragraphs
```

**Impact**: Eliminates the last remaining per-application LLM call. **100% free** resume + cover letter assembly after initial uploads.

### 19.10 Incremental ONNX Embedding Updates

When new KB entries are added, don't recompute all embeddings — only encode the new ones.

```python
def ensure_embeddings(self):
    """Compute embeddings for entries that don't have them yet."""
    missing = self.db.execute(
        "SELECT id, text FROM knowledge_base WHERE embedding IS NULL AND is_active = 1"
    ).fetchall()
    if not missing:
        return
    texts = [row["text"] for row in missing]
    embeddings = onnx_batch_encode(texts)  # batch encode
    for row, emb in zip(missing, embeddings):
        self.db.update_entry_embedding(row["id"], emb)
    logger.info("Computed embeddings for %d new entries", len(missing))
```

**Impact**: Adding 10 new entries from an upload computes 10 embeddings (~200ms), not 500.

---

## 20. Performance Budget Summary

| Operation | Before Optimization | After Optimization |
|-----------|--------------------|--------------------|
| Score 500 entries vs 1 JD | ~100ms (individual TF-IDF) | ~5ms (precomputed embeddings + vectorized) |
| Score 500 entries vs 20 JDs | ~2000ms | ~15ms (batch matrix multiply) |
| LaTeX compile (first time) | ~1-3s | ~1-3s (unavoidable) |
| LaTeX compile (cached) | ~1-3s | **<10ms** (hash cache hit) |
| Preview re-render (same entries) | ~1-3s | **<10ms** (cache) |
| Preview re-render (different template) | ~1-3s | ~1-3s (new compilation) |
| Document upload + extraction | 5-15s (blocking) | **instant return** + background processing |
| ONNX model load (cold start) | ~2s | ~2s (unavoidable, lazy-loaded once) |
| New entry embedding computation | ~100ms each | ~20ms each (batch) |
| Full bot cycle (20 jobs, KB assembly) | N/A (was 20 × 2 API calls) | **~500ms total** (batch score + cached PDFs) |

---

## 21. User Experience Enhancements

### 21.1 LinkedIn Profile Import (One-Click Onboarding)

Most users already have their career history on LinkedIn. Instead of manually uploading documents, offer a one-click import.

```
Settings → "Import from LinkedIn"
  │
  ├─→ User exports LinkedIn data (Settings → Get a copy of your data → Profile)
  │   LinkedIn provides a ZIP with: Profile.csv, Positions.csv, Skills.csv, Education.csv, Certifications.csv
  │
  ├─→ User uploads the ZIP file
  │
  └─→ System parses CSVs → sends to LLM for bullet polishing → KB entries
```

Alternatively, since we already have Playwright and browser automation:
```
"Import from LinkedIn" button
  → Opens LinkedIn profile page in Playwright browser
  → Scrapes: positions, skills, education, certifications
  → Sends to LLM → KB entries
```

**Impact**: Zero manual effort onboarding. User goes from "just installed" to "ready to apply" in 2 minutes.

### 21.2 Guided KB Gap Analysis

After initial upload(s), show the user what's strong and what's weak in their KB.

```
┌─────────────────────────────────────────────────────────┐
│  📋 Knowledge Base Health Check                          │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Experience bullets:  ████████████████░░░░  34 entries   │
│  Skills:              ████████████░░░░░░░░  18 entries   │
│  Education:           ████████████████████   3 entries   │
│  Projects:            ████░░░░░░░░░░░░░░░░   4 entries   │
│  Summaries:           ██░░░░░░░░░░░░░░░░░░   2 entries   │
│  Certifications:      ░░░░░░░░░░░░░░░░░░░░   0 entries   │
│                                                          │
│  ⚠ Suggestions:                                          │
│  • Add more project descriptions (helps for startup roles)│
│  • No certifications found — add AWS/GCP/Azure certs     │
│  • Only 2 summaries — add more for different job types   │
│  • Missing job types: devops, ml_engineer                │
│                                                          │
│  [Upload More Documents]  [Add Entry Manually]           │
└─────────────────────────────────────────────────────────┘
```

**Impact**: User knows exactly what to add. No guesswork about "is my KB good enough?"

### 21.3 Smart Entry Suggestions

When user views a specific job posting, show which KB entries would be used AND suggest improvements.

```
┌─────────────────────────────────────────────────────────┐
│  Job: Senior Backend Engineer at Stripe                  │
│  Match Score: 82/100                                     │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ✅ Strong matches (will be included):                   │
│  • "Led migration to microservices, reducing..."  (0.91) │
│  • "Built REST API handling 10M requests/day"     (0.87) │
│  • "Python, Flask, PostgreSQL, AWS, Docker"       (0.85) │
│                                                          │
│  ⚠ Weak matches (borderline):                           │
│  • "Managed team of 5 engineers across..."        (0.62) │
│                                                          │
│  ❌ Missing from your KB:                                │
│  • JD mentions "payment processing" — no matching entry  │
│  • JD mentions "Ruby on Rails" — not in your skills      │
│  • JD mentions "distributed systems" — add experience    │
│                                                          │
│  💡 Quick Actions:                                       │
│  [Add "payment processing" entry]  [Preview Resume]      │
└─────────────────────────────────────────────────────────┘
```

**Impact**: User can quickly fill gaps before applying. Improves application quality over time.

### 21.4 Bullet Point Improvement Suggestions

Periodically (or on demand), offer to improve weak KB entries via LLM.

```python
IMPROVEMENT_PROMPT = """
You are a career coach. This resume bullet point is weak. Improve it.

Rules:
- Keep the same facts and metrics — do NOT invent new ones
- Make it more impactful: stronger verb, clearer result, better structure
- Format: "Verb + What + Metric + Context"
- Keep it to 1-2 lines maximum

Original: {original_text}
Improved:
"""
```

UI flow:
```
KB Viewer → entry with low effectiveness_score
  → "Improve this entry" button
  → LLM generates improved version
  → Show side-by-side: original vs improved
  → User approves → replaces in KB (or keeps both)
```

**Impact**: KB quality improves over time. One LLM call to improve a bullet that gets reused 50 times.

### 21.5 Resume Score Explanation

When previewing a resume, show WHY each entry was selected and its relevance score.

```
Preview sidebar:
  ☑ [0.91] Led migration to microservices, reducing deploy time by 60%
           ↳ Matches: "microservices", "backend", "scalability"
  ☑ [0.87] Built REST API handling 10M requests/day
           ↳ Matches: "API", "high-throughput", "backend"
  ☐ [0.45] Implemented responsive dashboard using React
           ↳ Low: JD is backend-focused, this is frontend
```

**Impact**: User understands the system's decisions. Can manually override (toggle entries on/off) with confidence.

### 21.6 Quick-Add from Job Description

When viewing a JD that reveals a gap, user can quickly add a KB entry without leaving the flow.

```
In gap analysis: "JD mentions 'payment processing' — no matching entry"
  → [Quick Add] button opens inline form:
      Category: [Experience ▾]
      Subsection: [Senior Eng — Acme Corp ▾]  (dropdown of existing subsections)
      Text: [Integrated Stripe payment gateway processing $2M monthly transactions_]
      Job Types: [☑ backend  ☑ fullstack  ☐ frontend  ☐ devops]
      → [Save to KB]
```

**Impact**: Fastest possible path from "I need this bullet" to "it's in my KB". No file upload, no LLM wait.

### 21.7 Application History Insights

Surface patterns from past applications to help user make better decisions.

```
┌─────────────────────────────────────────────────────────┐
│  📊 Application Insights                                 │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Your best-performing bullets:                           │
│  1. "Led migration to microservices..." → 4/5 interviews │
│  2. "Reduced infrastructure costs by 40%..." → 3/4       │
│  3. "Mentored 3 junior engineers..." → 3/5               │
│                                                          │
│  Your weakest bullets:                                   │
│  1. "Participated in agile ceremonies" → 0/8 interviews  │
│     💡 Consider removing or improving this entry          │
│                                                          │
│  Job types with highest interview rate:                  │
│  • Backend: 45% (9/20)                                   │
│  • Fullstack: 30% (3/10)                                 │
│  • DevOps: 20% (1/5)                                     │
│                                                          │
│  Average resume assembly score for interviews: 0.82      │
│  Average resume assembly score for rejections: 0.68      │
│  → Suggestion: raise reuse_threshold to 0.80             │
└─────────────────────────────────────────────────────────┘
```

**Impact**: Data-driven career guidance. Users focus on what actually works.

### 21.8 One-Click Reoptimize

After updating the KB (new uploads, manual edits, removed weak bullets), user can reoptimize all pending/future applications.

```
KB updated → Banner: "Your knowledge base has changed.
  3 pending applications could benefit from updated resumes."
  [Reoptimize All]
```

Reoptimize: re-run assembly for pending applications with updated KB entries. Show diff of old vs new resume.

### 21.9 Setup Wizard Integration

Integrate KB onboarding into the existing setup wizard (first-run experience).

```
Step 1: Profile (name, email, phone)          ← existing
Step 2: Upload your career documents           ← NEW
        "Drop your resume, LinkedIn export,
         project descriptions — anything that
         describes your experience."
        [Upload Zone]
        Processing: ████████████░░░░ 3 of 4 files...
Step 3: Review Knowledge Base                  ← NEW
        "We extracted 47 entries from your documents.
         Review and edit anything that looks off."
        [KB Table with edit buttons]
Step 4: Choose Resume Template                 ← NEW
        [4 template thumbnails to click]
        [Live preview with your actual data]
Step 5: Search Preferences                     ← existing
Step 6: AI Provider (for cover letters)        ← existing, now optional
```

**Impact**: User goes from install → ready to apply in 5 minutes with a complete KB, chosen template, and previewed resume.

---

## 22. Manual KB Editing

Users must be able to edit, rephrase, or rewrite any KB entry directly. The LLM's extraction is a starting point, not final.

### Inline Edit in KB Viewer

```
KB Table Row:
┌──────────┬───────────────────────────────────────────┬──────────┐
│ Category │ Text                                      │ Actions  │
├──────────┼───────────────────────────────────────────┼──────────┤
│ exp      │ Led migration to microservices, reducing  │ ✏️ 🗑️    │
│          │ deploy time by 60%                        │          │
└──────────┴───────────────────────────────────────────┴──────────┘
                          │ Click ✏️
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ Edit Entry                                                [Save]│
├─────────────────────────────────────────────────────────────────┤
│ Category: [Experience ▾]                                        │
│                                                                 │
│ Subsection: [Senior Engineer — Acme Corp (2020-2023)___]        │
│                                                                 │
│ Text:                                                           │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ Spearheaded monolith-to-microservices migration across 12   │ │
│ │ services, cutting deployment time from 45min to 8min (82%   │ │
│ │ reduction) and eliminating 3h/week of manual deploy effort  │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
│ Job Types: [☑ backend  ☑ devops  ☐ frontend  ☐ data]           │
│                                                                 │
│ Tags: [python] [microservices] [deployment] [+add]             │
│                                                                 │
│ [Cancel]  [Save]  [Save & Preview Resume]                      │
└─────────────────────────────────────────────────────────────────┘
```

### Edit API

```
PUT /api/kb/entries/<id>
  Body: {
    "text": "Updated bullet text...",
    "category": "experience",
    "subsection": "Senior Engineer — Acme Corp (2020-2023)",
    "job_types": ["backend", "devops"],
    "tags": ["python", "microservices"]
  }
  Response: { "id": 5, "updated": true }
```

### Edit Behaviors
- Editing text **invalidates** the cached ONNX embedding (re-computed on next scoring run)
- Editing text **invalidates** any cached PDFs that used this entry (cache busted by content hash)
- Edit history tracked: `updated_at` timestamp updated, original text logged at DEBUG level
- User can also **duplicate** an entry (create a variant for a different job type) and **merge** two similar entries

### Bulk Edit
- Multi-select entries → "Edit Tags" → apply job_types/tags to all selected
- Multi-select → "Change Category" → reclassify entries
- Multi-select → "Delete" → soft-delete (set is_active=0)

---

## 23. Strict One-Page Resume Mode

Recruiters and ATS systems strongly prefer single-page resumes. This mode enforces it.

### Config

```python
class LatexConfig(BaseModel):
    template: str = "classic"
    font_family: str = "helvetica"
    font_size: int = 11
    margin: str = "0.75in"
    one_page_mode: bool = True          # NEW — default ON
    max_experience_bullets: int = 12    # hard cap on experience entries
    max_skills_lines: int = 3           # cap skill section length
```

### How It Works

```python
# In resume_assembler.py

# Page capacity estimation (conservative, accounts for LaTeX spacing)
PAGE_CAPACITY = {
    # (font_size, margin) → approximate content lines per page
    (10, "0.5in"): 55,
    (10, "0.75in"): 48,
    (11, "0.75in"): 44,
    (11, "1in"): 38,
    (12, "0.75in"): 40,
    (12, "1in"): 34,
}

LINE_ESTIMATES = {
    "contact": 2,           # name + contact line
    "summary": 3,           # 2-3 sentence summary
    "section_header": 2,    # "Experience" + rule + spacing
    "subsection_header": 1, # "Senior Eng — Acme (2020-2023)"
    "bullet_short": 1,      # < 80 chars
    "bullet_long": 2,       # 80-160 chars
    "bullet_very_long": 3,  # > 160 chars
    "skills": 2,            # comma-separated line
    "education_entry": 1,
    "certification_entry": 1,
}

def _select_entries_one_page(scored_entries, latex_config):
    """Select entries that fit on exactly one page."""
    capacity = PAGE_CAPACITY.get(
        (latex_config.font_size, latex_config.margin), 44
    )

    # Fixed sections first (always included)
    used_lines = 0
    used_lines += LINE_ESTIMATES["contact"]                    # 2
    used_lines += LINE_ESTIMATES["section_header"]             # Experience header
    used_lines += LINE_ESTIMATES["section_header"]             # Skills header
    used_lines += LINE_ESTIMATES["skills"]                     # Skills content
    used_lines += LINE_ESTIMATES["section_header"]             # Education header

    # Add education (always included, personal facts)
    education = [e for e in scored_entries if e.category == "education"]
    for edu in education:
        used_lines += LINE_ESTIMATES["education_entry"]

    # Add certifications (if they fit)
    certs = [e for e in scored_entries if e.category == "certification"]

    # Add best summary (if available)
    summaries = [e for e in scored_entries if e.category == "summary"]
    if summaries:
        used_lines += LINE_ESTIMATES["section_header"] + LINE_ESTIMATES["summary"]

    # Remaining space for experience bullets
    remaining = capacity - used_lines
    experience = sorted(
        [e for e in scored_entries if e.category == "experience"],
        key=lambda e: e.score, reverse=True
    )

    selected_exp = []
    current_subsection = None
    for entry in experience:
        # Estimate lines for this bullet
        bullet_lines = _estimate_bullet_lines(entry.text)
        # Add subsection header if new
        if entry.subsection != current_subsection:
            bullet_lines += LINE_ESTIMATES["subsection_header"]
            current_subsection = entry.subsection

        if remaining - bullet_lines >= 0:
            selected_exp.append(entry)
            remaining -= bullet_lines

        if len(selected_exp) >= latex_config.max_experience_bullets:
            break

    # If space remains, add certifications
    if remaining > LINE_ESTIMATES["section_header"] + 1:
        for cert in certs:
            if remaining - 1 >= 0:
                selected_exp.append(cert)
                remaining -= 1

    return selected_exp + education + summaries
```

### Compile-Time Validation

Even with line estimation, LaTeX rendering might overflow. Validate after compilation:

```python
def validate_one_page(pdf_path: Path) -> bool:
    """Check that compiled PDF is exactly one page."""
    from PyPDF2 import PdfReader
    reader = PdfReader(str(pdf_path))
    return len(reader.pages) == 1

# If validation fails (rare, estimation was off):
# 1. Remove lowest-scored bullet
# 2. Recompile
# 3. Repeat until 1 page (max 3 retries)
```

### UI Indicator

In preview modal, show page count badge:
```
[1 page ✓]  — green badge, good
[2 pages ⚠]  — yellow badge, auto-trimming...
```

User can toggle "Strict One Page" in settings. When ON, assembler enforces 1 page. When OFF, resume can be multi-page (some senior roles prefer 2-page CVs).

---

## 24. Manual Resume Builder (Drag-and-Drop)

Users should be able to manually craft a resume by picking entries from their KB — not just relying on the auto-scorer.

### Resume Builder UI

```
┌─────────────────────────────────────────────────────────────────┐
│  Resume Builder                                    [Save] [✕]   │
├──────────────────────────┬──────────────────────────────────────┤
│                          │                                      │
│  KNOWLEDGE BASE          │  YOUR RESUME                        │
│  (drag from here)        │  (drop here)                        │
│                          │                                      │
│  🔍 Search entries...    │  ┌────────────────────────────────┐  │
│  [Experience ▾] [All ▾]  │  │ 📋 Summary                     │  │
│                          │  │ ┌──────────────────────────┐   │  │
│  ┌──────────────────┐    │  │ │ Drop summary here...     │   │  │
│  │ ≡ Led migration  │◄───┤──│ └──────────────────────────┘   │  │
│  │   to microserv.. │drag│  │                                │  │
│  ├──────────────────┤    │  │ 📋 Experience                  │  │
│  │ ≡ Built REST API │    │  │ ┌──────────────────────────┐   │  │
│  │   handling 10M.. │    │  │ │ Sr Eng — Acme (2020-23)  │   │  │
│  ├──────────────────┤    │  │ │ • Led migration to micro │   │  │
│  │ ≡ Reduced infra  │    │  │ │ • Managed team of 5 eng  │   │  │
│  │   costs by 40%.. │    │  │ │                          │   │  │
│  ├──────────────────┤    │  │ │ [+ Drop more bullets]    │   │  │
│  │ ≡ Mentored 3 jr  │    │  │ └──────────────────────────┘   │  │
│  │   engineers...   │    │  │ ┌──────────────────────────┐   │  │
│  └──────────────────┘    │  │ │ Frontend — Startup (2018)│   │  │
│                          │  │ │ • Built dashboard with.. │   │  │
│  ── Skills ──            │  │ │ [+ Drop more bullets]    │   │  │
│  ┌──────────────────┐    │  │ └──────────────────────────┘   │  │
│  │ ≡ Python, Flask,  │    │  │                                │  │
│  │   Django, AWS...  │    │  │ 📋 Skills                      │  │
│  ├──────────────────┤    │  │ Python, Flask, AWS, Docker     │  │
│  │ ≡ React, TS,     │    │  │                                │  │
│  │   Tailwind...    │    │  │ 📋 Education                   │  │
│  └──────────────────┘    │  │ BS CS — MIT (2016)             │  │
│                          │  └────────────────────────────────┘  │
│  ── Education ──         │                                      │
│  ┌──────────────────┐    │  Page: [1/1 ✓]  Bullets: 8/12      │
│  │ ≡ BS CS — MIT     │    │                                      │
│  └──────────────────┘    │  [Preview PDF]  [Auto-Fill for JD]  │
│                          │  [Save as Template]  [Apply to Job]  │
└──────────────────────────┴──────────────────────────────────────┘
```

### Interactions

**Drag & Drop**:
- Left panel: KB entries grouped by category, searchable, filterable
- Right panel: Resume sections with drop zones
- Drag entry from left → drop into section on right
- Reorder bullets within a section by dragging up/down
- Remove entry by dragging back to left or clicking ✕

**Auto-Fill for JD**:
- Paste a JD URL or text → system auto-selects best entries
- User reviews and adjusts (add/remove/reorder)
- Hybrid of auto + manual control

**One-Page Indicator**:
- Live counter: "Page: 1/1 ✓" or "Page: 2/1 ⚠ Remove 3 bullets"
- In one-page mode, drop zones gray out when page is full
- Tooltip: "Remove an entry to make room"

**Save Options**:
- "Save as Template" → saves the entry ID combination as a reusable preset (e.g., "My Backend Resume", "My Fullstack Resume")
- "Apply to Job" → links this combination to a specific job application
- "Preview PDF" → live preview with chosen template

### Resume Builder API

```
POST /api/resumes/build
  Body: {
    "entry_ids": [1, 5, 12, 34, 50, 51],    // ordered
    "template": "modern",
    "latex_config": { "font_size": 11, ... },
    "name": "My Backend Resume"               // optional preset name
  }
  Response: {
    "preview_url": "/api/resumes/preview/abc123",
    "page_count": 1,
    "entry_count": 12
  }

GET /api/resumes/presets
  Response: [
    {"id": 1, "name": "My Backend Resume", "entry_ids": [...], "template": "modern", "created_at": "..."},
    {"id": 2, "name": "My Fullstack Resume", "entry_ids": [...], "template": "classic", "created_at": "..."}
  ]

POST /api/resumes/presets
  Body: { "name": "My DevOps Resume", "entry_ids": [...], "template": "minimal" }

DELETE /api/resumes/presets/<id>
```

### Resume Presets Table

```sql
CREATE TABLE resume_presets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    entry_ids TEXT NOT NULL,         -- JSON array: '[1, 5, 12, 34]'
    template TEXT NOT NULL DEFAULT 'classic',
    latex_config TEXT,               -- JSON: font, size, margin overrides
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME
);
```

**Impact**: Power users who want full control can handcraft perfect resumes. Casual users still use auto-assembly. Presets mean you build it once and reuse across similar jobs.

---

## 25. ATS Resume Scoring Algorithm

### Background: How Real ATS Systems Work

There is no single published algorithm. Each vendor (Workday, Greenhouse, Lever, Taleo, iCIMS) uses proprietary scoring. However, from reverse-engineering, recruiter feedback, and published research, the common patterns are:

1. **Keyword extraction** from JD (required vs preferred skills)
2. **Resume parsing** into structured fields (experience, skills, education)
3. **Keyword matching** (exact + synonym) with weights on required vs preferred
4. **Knockout filters** (years of experience, education level, certifications)
5. **Ranking** by weighted match score

Since we can't replicate a specific ATS, we build a **composite scorer** that covers what all ATS systems check — optimizing for the common denominator.

### 25.1 JD Keyword Extraction Algorithm

```python
# core/jd_analyzer.py

def analyze_jd(jd_text: str) -> JDAnalysis:
    """Extract structured requirements from a job description."""

    # Step 1: Section detection
    # JDs typically have: About/Description, Requirements, Preferred, Responsibilities
    sections = _split_jd_sections(jd_text)

    # Step 2: Extract keywords per category
    required_skills = _extract_from_section(sections.get("requirements", ""))
    preferred_skills = _extract_from_section(sections.get("preferred", ""))
    responsibilities = _extract_from_section(sections.get("responsibilities", ""))

    # If no clear sections, treat entire JD as mixed
    if not required_skills and not preferred_skills:
        all_keywords = _extract_keywords(jd_text)
        # Heuristic: words appearing 2+ times are likely "required"
        required_skills = [kw for kw in all_keywords if all_keywords[kw] >= 2]
        preferred_skills = [kw for kw in all_keywords if all_keywords[kw] == 1]

    return JDAnalysis(
        required_skills=required_skills,
        preferred_skills=preferred_skills,
        responsibilities=responsibilities,
        job_title=_extract_title(jd_text),
        experience_years=_extract_years(jd_text),
        education_level=_extract_education(jd_text),
    )
```

#### Section Detection

JDs follow predictable patterns. Detect sections by heading keywords:

```python
SECTION_PATTERNS = {
    "requirements": [
        r"(?i)(required|minimum|must.have|qualifications|what you.ll need|requirements)",
    ],
    "preferred": [
        r"(?i)(preferred|nice.to.have|bonus|plus|desired|ideally)",
    ],
    "responsibilities": [
        r"(?i)(responsibilities|what you.ll do|role|duties|day.to.day)",
    ],
    "about": [
        r"(?i)(about|overview|description|who we are|the role)",
    ],
}

def _split_jd_sections(jd_text: str) -> dict[str, str]:
    """Split JD into sections based on heading patterns."""
    # Find section boundaries by matching headings
    # Return dict: {"requirements": "...", "preferred": "...", ...}
```

#### Keyword Extraction (Multi-Layer)

```python
def _extract_keywords(text: str) -> dict[str, int]:
    """Extract technology keywords, skills, and qualifications from text."""

    keywords = Counter()

    # Layer 1: Known tech dictionary (fast, high precision)
    # ~500 terms: programming languages, frameworks, tools, platforms
    for term in TECH_DICTIONARY:
        # Case-insensitive but respect word boundaries
        # "go" should match "Go" but not "going"
        pattern = rf"\b{re.escape(term)}\b"
        count = len(re.findall(pattern, text, re.IGNORECASE))
        if count:
            keywords[term.lower()] = count

    # Layer 2: N-gram extraction for multi-word terms
    # "machine learning", "distributed systems", "project management"
    bigrams = _extract_ngrams(text, n=2)
    trigrams = _extract_ngrams(text, n=3)
    for ngram, count in (bigrams + trigrams):
        if ngram.lower() in KNOWN_PHRASES:
            keywords[ngram.lower()] = count

    # Layer 3: Years of experience patterns
    # "5+ years of experience", "3-5 years", "minimum 3 years"
    years_patterns = re.findall(
        r"(\d+)\+?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience|exp)",
        text, re.IGNORECASE
    )

    # Layer 4: Education patterns
    # "Bachelor's", "Master's", "PhD", "BS/MS in Computer Science"
    education = re.findall(
        r"(?i)(bachelor|master|phd|doctorate|bs|ms|mba|b\.s\.|m\.s\.)",
        text
    )

    # Layer 5: Certification patterns
    # "AWS Certified", "PMP", "CKA", "CISSP"
    certs = [term for term in CERT_DICTIONARY if term.lower() in text.lower()]

    return keywords

# Tech dictionary (curated, ~500 entries)
TECH_DICTIONARY = {
    # Languages
    "Python", "JavaScript", "TypeScript", "Java", "C++", "C#", "Go", "Rust",
    "Ruby", "PHP", "Swift", "Kotlin", "Scala", "R", "MATLAB", "SQL",
    # Frameworks
    "React", "Vue", "Angular", "Next.js", "Django", "Flask", "FastAPI",
    "Spring", "Express", "Rails", "Laravel", ".NET", "Svelte",
    # Databases
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch",
    "DynamoDB", "Cassandra", "SQLite", "Firestore",
    # Cloud/DevOps
    "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform",
    "Jenkins", "GitHub Actions", "CircleCI", "Ansible",
    # Tools
    "Git", "Jira", "Confluence", "Figma", "Datadog", "Splunk",
    "Grafana", "Prometheus", "Kafka", "RabbitMQ", "Airflow",
    # Concepts
    "REST", "GraphQL", "gRPC", "microservices", "CI/CD",
    "agile", "scrum", "TDD", "machine learning", "deep learning",
    # ... (~500 total)
}

KNOWN_PHRASES = {
    "machine learning", "deep learning", "natural language processing",
    "computer vision", "distributed systems", "event driven",
    "project management", "product management", "data engineering",
    "data pipeline", "real time", "high availability",
    # ... (~200 total)
}

CERT_DICTIONARY = {
    "AWS Certified", "CKA", "CKAD", "PMP", "CISSP", "CEH",
    "Google Cloud Certified", "Azure Certified", "Terraform Associate",
    # ... (~50 total)
}
```

#### Synonym Matching

ATS systems use synonym dictionaries. We should too:

```python
SYNONYMS = {
    "javascript": ["js", "es6", "es2015", "ecmascript"],
    "typescript": ["ts"],
    "postgresql": ["postgres", "psql"],
    "kubernetes": ["k8s"],
    "amazon web services": ["aws"],
    "google cloud platform": ["gcp"],
    "continuous integration": ["ci", "ci/cd"],
    "machine learning": ["ml"],
    "artificial intelligence": ["ai"],
    "react.js": ["react", "reactjs"],
    "node.js": ["node", "nodejs"],
    "vue.js": ["vue", "vuejs"],
    # ... (~100 mappings)
}

def _normalize_keyword(kw: str) -> str:
    """Normalize a keyword to its canonical form."""
    kw_lower = kw.lower().strip()
    for canonical, aliases in SYNONYMS.items():
        if kw_lower in aliases or kw_lower == canonical:
            return canonical
    return kw_lower
```

### 25.2 Resume-vs-JD ATS Scoring Algorithm

After assembling a resume (from KB or LLM), score it against the analyzed JD:

```python
def score_resume_ats(
    resume_entries: list[KBEntry],
    jd_analysis: JDAnalysis,
    profile: UserProfile,
) -> ATSScore:
    """Score an assembled resume against a JD, simulating ATS behavior.

    Returns 0-100 score with detailed breakdown.
    """

    # Combine all resume text for keyword matching
    resume_text = " ".join(e.text for e in resume_entries)
    resume_skills = [e.text for e in resume_entries if e.category == "skill"]
    resume_experience = [e for e in resume_entries if e.category == "experience"]

    # --- Component 1: Required Keyword Coverage (35 points) ---
    required_matched = 0
    required_total = len(jd_analysis.required_skills)
    required_details = []
    for kw in jd_analysis.required_skills:
        normalized = _normalize_keyword(kw)
        found = _keyword_in_text(normalized, resume_text)
        if found:
            required_matched += 1
            required_details.append({"keyword": kw, "status": "found"})
        else:
            required_details.append({"keyword": kw, "status": "missing"})

    required_score = (required_matched / max(required_total, 1)) * 35

    # --- Component 2: Preferred Keyword Coverage (15 points) ---
    preferred_matched = 0
    preferred_total = len(jd_analysis.preferred_skills)
    for kw in jd_analysis.preferred_skills:
        if _keyword_in_text(_normalize_keyword(kw), resume_text):
            preferred_matched += 1

    preferred_score = (preferred_matched / max(preferred_total, 1)) * 15

    # --- Component 3: Experience Relevance (25 points) ---
    # Semantic similarity between experience bullets and JD responsibilities
    if jd_analysis.responsibilities:
        relevance_scores = []
        for entry in resume_experience:
            sim = score_text_similarity(entry.text, " ".join(jd_analysis.responsibilities))
            relevance_scores.append(sim)
        avg_relevance = mean(relevance_scores) if relevance_scores else 0
    else:
        avg_relevance = 0.5  # no responsibilities section, give benefit of doubt

    relevance_score = avg_relevance * 25

    # --- Component 4: Title Alignment (15 points) ---
    # Does resume content reflect the target job title?
    title_sim = score_text_similarity(
        jd_analysis.job_title,
        " ".join(e.subsection or "" for e in resume_experience) + " " +
        " ".join(e.text for e in resume_entries if e.category == "summary")
    )
    title_score = title_sim * 15

    # --- Component 5: Qualification Match (10 points) ---
    qual_score = 0
    # Education level check (5 points)
    if jd_analysis.education_level:
        user_education = [e.text for e in resume_entries if e.category == "education"]
        if _education_meets_requirement(user_education, jd_analysis.education_level):
            qual_score += 5
    else:
        qual_score += 5  # no requirement = automatic pass

    # Years of experience check (5 points)
    if jd_analysis.experience_years:
        if _experience_meets_years(resume_experience, jd_analysis.experience_years):
            qual_score += 5
    else:
        qual_score += 5

    # --- Total ---
    total = required_score + preferred_score + relevance_score + title_score + qual_score

    return ATSScore(
        total=round(total),
        breakdown={
            "required_keywords": {"score": round(required_score), "max": 35,
                                   "matched": required_matched, "total": required_total,
                                   "details": required_details},
            "preferred_keywords": {"score": round(preferred_score), "max": 15,
                                    "matched": preferred_matched, "total": preferred_total},
            "experience_relevance": {"score": round(relevance_score), "max": 25,
                                      "avg_similarity": round(avg_relevance, 2)},
            "title_alignment": {"score": round(title_score), "max": 15,
                                 "similarity": round(title_sim, 2)},
            "qualifications": {"score": round(qual_score), "max": 10},
        },
        missing_required=[d["keyword"] for d in required_details if d["status"] == "missing"],
    )
```

### 25.3 Scoring Breakdown UI

```
┌─────────────────────────────────────────────────────────────────┐
│  ATS Score: 82/100                                    [Strong]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Required Keywords          ████████████████░░░░  28/35  (8/10) │
│    ✅ Python  ✅ Flask  ✅ PostgreSQL  ✅ AWS  ✅ Docker          │
│    ✅ REST API  ✅ microservices  ✅ CI/CD                       │
│    ❌ Kubernetes  ❌ GraphQL                                     │
│                                                                  │
│  Preferred Keywords         ████████████████████  15/15  (5/5)  │
│    ✅ Terraform  ✅ Redis  ✅ monitoring  ✅ agile  ✅ mentoring  │
│                                                                  │
│  Experience Relevance       ████████████████░░░░  20/25  (0.80) │
│    Your experience bullets align well with the role.             │
│    Strongest match: "Led migration to microservices..."          │
│                                                                  │
│  Title Alignment            ████████████░░░░░░░░  10/15  (0.67) │
│    JD: "Senior Backend Engineer"                                 │
│    Your titles: "Senior Engineer", "Software Engineer"           │
│    💡 Consider adding "Backend" to your summary                  │
│                                                                  │
│  Qualifications             ██████████████████████ 10/10         │
│    ✅ Education: BS meets "Bachelor's" requirement               │
│    ✅ Experience: 6 years meets "5+ years" requirement           │
│                                                                  │
│  ──────────────────────────────────────────────────────────────  │
│  💡 To improve:                                                  │
│  • Add Kubernetes experience (required keyword, missing)         │
│  • Add GraphQL experience (required keyword, missing)            │
│  • Include "Backend" in your summary for better title alignment  │
│                                                                  │
│  [Add Missing Keywords to KB]  [Auto-Optimize Resume]           │
└─────────────────────────────────────────────────────────────────┘
```

### 25.4 Score Integration Points

| Where | What's Shown |
|-------|-------------|
| **Bot review mode** | ATS score shown before approve/skip decision |
| **Resume preview** | ATS score panel alongside PDF viewer |
| **Resume builder** | Live ATS score updates as entries are added/removed |
| **Application tracker** | ATS score column in applications table |
| **Analytics dashboard** | Correlation: ATS score vs interview rate |

### 25.5 Platform-Specific ATS Profiles

Since our app already detects which ATS platform a job uses (`detect_ats()` in `core/filter.py` — Workday, Greenhouse, Lever, LinkedIn, Indeed, Ashby), we tailor resume optimization per platform.

#### What's Publicly Known Per Platform

**Workday (most aggressive auto-screening)**
- Source: Workday's own documentation, recruiter forums, jobscan.co research
- Uses "screening questions" + keyword matching against required qualifications
- Recruiters configure "must-have" vs "nice-to-have" skills in the job requisition
- Resume parsed into structured fields — formatting matters heavily
- **Our approach**: Extract keywords from the "Qualifications" section of the JD (Workday JDs have predictable structure). Weight required skills at 2x preferred. Ensure resume uses exact phrasing from JD (not synonyms — Workday's parser is more literal).

**Greenhouse (lighter auto-screening, scorecard-driven)**
- Source: Greenhouse's published hiring philosophy, API docs, recruiter interviews
- Less automated scoring — recruiters build scorecards with custom criteria
- But initial screen often uses "Auto-Reject" rules based on knockout questions
- Resume is parsed but scoring is mostly human-driven
- **Our approach**: Focus on keyword coverage (no knockout gaps) and clean formatting. Less aggressive optimization needed.

**Lever (similar to Greenhouse)**
- Source: Lever's documentation, recruiter community
- "Opportunity" based workflow. Light auto-screening.
- Tags and sources matter more than resume parsing
- **Our approach**: Ensure cover letter is strong (Lever shows it prominently). Resume keyword coverage standard.

**LinkedIn Easy Apply (algorithmic matching)**
- Source: LinkedIn's published matching algorithm papers, engineering blog
- Uses ML-based matching: job title similarity, skills endorsements, experience overlap
- Considers profile completeness, skill endorsements, headline
- Resume upload is secondary to LinkedIn profile data
- **Our approach**: Ensure resume title/summary closely matches JD title. Include LinkedIn-style skills section. Optimize for the specific keywords in the JD since LinkedIn's system does compare uploaded resumes.

**Indeed (Smart Apply + resume scoring)**
- Source: Indeed's published hiring platform docs, employer-side documentation
- Indeed assigns an internal match score visible to employers
- Weighs: job title match, location, salary expectations, skills, experience duration
- Resume parsed by Indeed's own parser — prefers simple formatting
- **Our approach**: Simple formatting (no columns, no graphics). Job title in summary should mirror JD title closely. Include years of experience explicitly.

**Taleo/Oracle (legacy but still widespread)**
- Source: Extensive community research, taleo.help forums, HR community
- Most aggressive keyword matching of all ATS
- Ranks candidates by % keyword match against job requisition
- Known to penalize: creative formatting, headers/footers, tables, images
- **Our approach**: Maximum keyword density. Plain formatting. Repeat critical keywords in multiple sections (summary + experience + skills).

#### Platform Profile Implementation

```python
# core/ats_profiles.py

@dataclass
class ATSProfile:
    name: str
    keyword_weight_required: float     # how much to weight required kw match
    keyword_weight_preferred: float
    title_match_weight: float
    formatting_strictness: str          # "strict" | "moderate" | "relaxed"
    synonym_tolerance: bool             # does this ATS understand synonyms?
    keyword_density_matters: bool       # should we repeat keywords?
    cover_letter_weight: str            # "high" | "medium" | "low"
    tips: list[str]                     # platform-specific tips for user

ATS_PROFILES = {
    "workday": ATSProfile(
        name="Workday",
        keyword_weight_required=2.0,
        keyword_weight_preferred=0.8,
        title_match_weight=1.5,
        formatting_strictness="strict",
        synonym_tolerance=False,        # use exact JD phrasing
        keyword_density_matters=True,
        cover_letter_weight="low",
        tips=[
            "Use exact keywords from the job posting — Workday matches literally",
            "Include required skills in both Experience and Skills sections",
            "Keep formatting simple — Workday's parser struggles with complex layouts",
        ],
    ),
    "greenhouse": ATSProfile(
        name="Greenhouse",
        keyword_weight_required=1.2,
        keyword_weight_preferred=1.0,
        title_match_weight=1.0,
        formatting_strictness="moderate",
        synonym_tolerance=True,
        keyword_density_matters=False,
        cover_letter_weight="medium",
        tips=[
            "Greenhouse relies more on recruiter review than auto-scoring",
            "A strong cover letter gets seen — Greenhouse displays it prominently",
            "Ensure no knockout keyword gaps — recruiters use scorecards",
        ],
    ),
    "lever": ATSProfile(
        name="Lever",
        keyword_weight_required=1.0,
        keyword_weight_preferred=1.0,
        title_match_weight=1.0,
        formatting_strictness="moderate",
        synonym_tolerance=True,
        keyword_density_matters=False,
        cover_letter_weight="high",
        tips=[
            "Lever shows your cover letter alongside your resume",
            "Write a compelling cover letter — it matters more here",
        ],
    ),
    "linkedin": ATSProfile(
        name="LinkedIn",
        keyword_weight_required=1.5,
        keyword_weight_preferred=1.2,
        title_match_weight=2.0,         # LinkedIn heavily weights title match
        formatting_strictness="relaxed",
        synonym_tolerance=True,
        keyword_density_matters=False,
        cover_letter_weight="low",
        tips=[
            "LinkedIn weighs job title similarity very heavily",
            "Include the exact job title from the posting in your summary",
            "Skills section is matched against LinkedIn's skills taxonomy",
        ],
    ),
    "indeed": ATSProfile(
        name="Indeed",
        keyword_weight_required=1.5,
        keyword_weight_preferred=0.8,
        title_match_weight=1.8,
        formatting_strictness="strict",
        synonym_tolerance=False,
        keyword_density_matters=True,
        cover_letter_weight="low",
        tips=[
            "Indeed's parser prefers simple, single-column formatting",
            "Include years of experience as a number (e.g., '5+ years')",
            "Job title in your summary should closely mirror the posting",
        ],
    ),
    "ashby": ATSProfile(
        name="Ashby",
        keyword_weight_required=1.0,
        keyword_weight_preferred=1.0,
        title_match_weight=1.0,
        formatting_strictness="moderate",
        synonym_tolerance=True,
        keyword_density_matters=False,
        cover_letter_weight="medium",
        tips=[
            "Ashby is newer and relies more on recruiter workflows",
            "Standard keyword coverage is sufficient",
        ],
    ),
}

# Fallback for unknown platforms
DEFAULT_PROFILE = ATSProfile(
    name="Generic ATS",
    keyword_weight_required=1.5,
    keyword_weight_preferred=1.0,
    title_match_weight=1.5,
    formatting_strictness="strict",    # assume worst case
    synonym_tolerance=False,           # assume literal matching
    keyword_density_matters=True,
    cover_letter_weight="medium",
    tips=[
        "Unknown ATS — optimizing for strictest common denominator",
        "Use exact keywords from the job description",
        "Keep formatting simple and single-column",
    ],
)
```

#### Platform-Aware Scoring

The ATS scoring function (25.2) is modified to use the platform profile:

```python
def score_resume_ats(resume_entries, jd_analysis, profile, platform="generic"):
    """Score resume against JD using platform-specific ATS profile."""
    ats_profile = ATS_PROFILES.get(platform, DEFAULT_PROFILE)

    # Adjust weights based on platform
    required_max = 35 * ats_profile.keyword_weight_required
    preferred_max = 15 * ats_profile.keyword_weight_preferred
    title_max = 15 * ats_profile.title_match_weight

    # Normalize back to 100 scale
    total_max = required_max + preferred_max + 25 + title_max + 10
    scale = 100 / total_max

    # ... scoring logic with platform-specific synonym tolerance,
    #     keyword density checks, etc.
```

#### Platform-Aware Resume Assembly

When assembling a resume for a specific platform, the assembler adjusts:

```python
def assemble_resume(jd_text, kb, profile, reuse_config, latex_config, platform="generic"):
    ats_profile = ATS_PROFILES.get(platform, DEFAULT_PROFILE)

    # If platform doesn't tolerate synonyms, prefer entries with EXACT JD keywords
    if not ats_profile.synonym_tolerance:
        # Boost score for entries containing exact JD phrases
        ...

    # If keyword density matters, repeat critical skills in summary + experience
    if ats_profile.keyword_density_matters:
        # Ensure top required keywords appear in 2+ sections
        ...

    # If formatting is strict, use simplest LaTeX template
    if ats_profile.formatting_strictness == "strict":
        latex_config.template = "classic"  # simplest, most ATS-parseable
```

#### Platform Tips in UI

```
Resume Preview for: Senior Backend Engineer at Stripe
Platform detected: Greenhouse

┌─────────────────────────────────────────────────────────┐
│  💡 Greenhouse Tips:                                     │
│  • Greenhouse relies more on recruiter review            │
│  • A strong cover letter gets seen here — invest time    │
│  • Ensure no knockout keyword gaps                       │
└─────────────────────────────────────────────────────────┘
```

### 25.6 "Auto-Optimize" Feature

Combines ATS scoring + platform profile to automatically maximize the resume. When ATS score is below target, offer one-click optimization:

```python
def auto_optimize_resume(current_entries, jd_analysis, kb, target_score=85):
    """Swap/add KB entries to maximize ATS score."""

    current_score = score_resume_ats(current_entries, jd_analysis)
    if current_score.total >= target_score:
        return current_entries  # already good

    # For each missing required keyword:
    for missing_kw in current_score.missing_required:
        # Find a KB entry containing this keyword
        candidates = kb.search_by_keyword(missing_kw, category="experience")
        if candidates:
            # Swap out lowest-scored current entry for the candidate
            # (respecting one-page constraint)
            ...

    # Re-score and return optimized set
```

**Impact**: User sees "ATS Score: 72 → click Auto-Optimize → ATS Score: 88" with a clear diff of what changed.

---

## 26. Additional User-Facing Features

### 26.1 Job-Specific Cover Letter Assembly from KB

Same concept as resume assembly but for cover letters. The KB already stores summaries and experience narratives. Combine with JD analysis to assemble a cover letter without LLM:

```
Cover Letter Structure:
  Opening: Hook referencing company/role (from KB "cover_opening" entries)
  Body 1:  Most relevant experience narrative (top-scored KB "cover_body" entry)
  Body 2:  Technical alignment paragraph (assembled from KB experience bullets)
  Closing: Call to action (from KB "cover_closing" entries)
```

User uploads past cover letters → LLM extracts paragraphs → KB stores them tagged by tone/industry → Assembly picks best match per JD.

**Impact**: Eliminates the last per-application LLM call. 100% free assembly after onboarding.

### 26.2 Interview Prep from KB + JD

After applying, user needs to prepare for interviews. The app already stores the JD and knows which KB entries were used. Generate interview prep automatically:

```
┌──────────────────────────────────────────────────────────┐
│  🎯 Interview Prep: Senior Backend Engineer at Stripe     │
├──────────────────────────────────────────────────────────┤
│                                                           │
│  LIKELY QUESTIONS (based on JD keywords + your resume):   │
│                                                           │
│  Technical:                                               │
│  • "Tell me about your microservices migration"           │
│    ↳ Your bullet: "Led migration to microservices..."     │
│    ↳ Be ready: Why did you migrate? What challenges?      │
│                                                           │
│  • "How do you handle high-throughput APIs?"              │
│    ↳ Your bullet: "Built REST API handling 10M req/day"   │
│    ↳ Be ready: Caching strategy? Load balancing?          │
│                                                           │
│  Behavioral:                                              │
│  • "Tell me about a time you led a team"                  │
│    ↳ Your bullet: "Managed team of 5 engineers"           │
│    ↳ STAR format: Situation → Task → Action → Result      │
│                                                           │
│  GAP AREAS (JD mentions, not in your resume):             │
│  • "Payment processing" — prepare a story or be upfront   │
│  • "GraphQL" — read up on basics before the interview     │
│                                                           │
│  COMPANY RESEARCH:                                        │
│  • Stripe: payments infrastructure, developer-first       │
│  • Recent news: [auto-fetched if web access available]    │
└──────────────────────────────────────────────────────────┘
```

This is generated **locally** from KB entries + JD analysis — no LLM needed. Just pattern matching between JD requirements and your KB entries.

### 26.3 Application Status Tracking with Reminders

Enhance the existing application tracker with proactive reminders:

```
• Applied 3 days ago → "Follow up in 4 days if no response"
• Applied 7 days ago → "Consider sending a follow-up email"
• Interview scheduled → "Interview in 2 days — review prep notes"
• Rejected → "Similar role open at [company] — apply?"
• No response 14 days → "This one's likely cold — archive?"
```

Configurable reminder timelines in settings. Notifications via system tray / SocketIO toast.

### 26.4 Salary Insights per Application

When viewing a job, show salary context:

```
Job: Senior Backend Engineer at Stripe
Salary (from posting): $180,000 - $220,000

📊 Context from your application history:
  • Your average applied salary range: $160K - $200K
  • This role: 10% above your average (good match)
  • Similar roles you applied to: 12 applications
  • Interview rate for $180K+ roles: 35%
```

No external API needed — computed from the user's own application data in SQLite.

### 26.5 Duplicate Job Detection

Before applying, check if this JD is substantially similar to a job already applied to (different posting, same role/company or same JD at different company):

```python
def detect_duplicate_jd(new_jd: str, db: Database, threshold: float = 0.90) -> dict | None:
    """Check if a very similar JD exists in recent applications."""
    recent_jds = db.get_recent_job_descriptions(days=30)
    for app_id, old_jd_path in recent_jds:
        old_jd = Path(old_jd_path).read_text()
        similarity = score_text_similarity(new_jd, old_jd)
        if similarity >= threshold:
            return {"app_id": app_id, "similarity": similarity}
    return None
```

UI: "This looks 95% similar to a job you applied to 3 days ago at the same company. Skip?"

**Impact**: Prevents wasting applications on duplicate postings (common on LinkedIn/Indeed).

### 26.6 Resume Version Diff

When the auto-assembler picks different entries for two similar jobs, show what changed:

```
Resume for "Backend Eng at Stripe" vs "Backend Eng at Square"

Added:
  + "Integrated Stripe payment gateway processing $2M monthly"
  + "Payment processing, PCI compliance"

Removed:
  - "Built real-time analytics dashboard"
  - "Data visualization, D3.js"

Unchanged: 8 bullets, skills section, education
```

Helps user understand WHY the system made different choices for seemingly similar roles.

### 26.7 Weekly Application Summary Email/Report

Generate a weekly summary of application activity:

```
┌──────────────────────────────────────────────────────────┐
│  📊 Weekly Summary: Mar 4 - Mar 11                        │
├──────────────────────────────────────────────────────────┤
│                                                           │
│  Applications sent:     23                                │
│  From KB (no API cost): 18  (78% savings!)                │
│  From LLM:               5                                │
│  Interview invites:      3                                │
│  Rejections:             8                                │
│  Pending:               12                                │
│                                                           │
│  Top performing resume:  "Backend Senior" preset (2/5)    │
│  Weakest resume:         "Fullstack" preset (0/6)         │
│                                                           │
│  KB health:              47 entries, 3 new this week      │
│  Suggestion:  Your "Fullstack" resumes aren't landing.    │
│               Consider uploading more frontend projects.  │
│                                                           │
│  Estimated API cost saved: $4.32                          │
└──────────────────────────────────────────────────────────┘
```

Exportable as PDF or shown in the dashboard. No external service needed — all from local data.

### 26.8 Smart Job Bookmarking

When the bot finds jobs in "watch" or "review" mode, let users bookmark interesting ones for later:

```
Bot found: Senior Backend Eng at Stripe (Score: 92)
  [Apply Now]  [Bookmark 🔖]  [Skip]

Bookmarked jobs queue:
  • Sr Backend Eng at Stripe — saved 2 days ago (ATS score: 87)
  • Platform Eng at Datadog — saved 5 days ago (ATS score: 79)
  → [Batch Apply All]  [Review & Apply Individually]
```

Bookmarked jobs get their JDs saved + KB scoring precomputed so the user can batch-apply during off-hours.

### 26.9 Multi-Language Resume Support

For users applying internationally or to multilingual roles:

```
KB entries can be tagged with language: "en", "es", "de", "fr", etc.

Upload flow:
  User uploads Spanish resume → LLM extracts entries tagged language="es"
  User uploads English resume → entries tagged language="en"

Assembly:
  Job posting in Spanish → assemble from Spanish KB entries
  Job posting in English → assemble from English KB entries
  Mixed posting → primary language detection → match
```

Leverages existing i18n infrastructure (en.json, es.json locale files).

### 26.10 "Why Was I Rejected?" Analysis

When a user marks an application as "rejected", offer analysis:

```
Application rejected: Backend Eng at Stripe

Possible reasons (based on your data):
  • ATS Score was 72 — below the 85+ interview average for similar roles
  • Missing required keyword: "Kubernetes" (present in 80% of similar JDs)
  • Your resume had 6 experience bullets — interviews averaged 9+
  • Similar companies (Stripe, Square, Plaid) interviewed candidates with
    "payment" experience — not found in your KB

💡 Actions:
  [Add Kubernetes entry to KB]
  [Upload payment processing experience]
  [Improve "Fullstack" preset]
```

All computed from local data: compare rejected apps vs interviewed apps, find the delta.

---

## 27. Experience Timeline & Bullet Point Provenance

### 27.1 The Problem

Current KB schema stores `subsection` as a free-text string (e.g., "Senior Engineer — Acme Corp (2020-2023)"). This is insufficient because:

1. **No structured date parsing** — can't calculate "years of backend experience"
2. **No domain tracking** — a career changer with 3 years teaching + 2 years coding shows as "5 years experience" but has only 2 relevant years
3. **No role hierarchy** — can't distinguish between a bullet from an internship vs a senior role
4. **Bullets can be orphaned** — if a user edits the subsection text, the link to the original role breaks

### 27.2 Enhanced Schema: Roles Table + KB Linkage

Add a `roles` table as the source of truth for employment/education/project history. Every KB entry links to a specific role.

```sql
-- The user's career timeline
CREATE TABLE roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    -- 'employment', 'education', 'project', 'volunteer', 'freelance', 'certification'
    title TEXT NOT NULL,
    -- 'Senior Backend Engineer', 'BS Computer Science', 'E-commerce Platform'
    organization TEXT NOT NULL,
    -- 'Acme Corp', 'MIT', 'Personal Project'
    start_date TEXT NOT NULL,
    -- 'YYYY-MM' format: '2020-06'
    end_date TEXT,
    -- 'YYYY-MM' or NULL for current/ongoing
    is_current INTEGER NOT NULL DEFAULT 0,
    domain TEXT,
    -- Primary domain: 'backend', 'frontend', 'fullstack', 'data', 'devops',
    -- 'management', 'teaching', 'sales', 'design', etc.
    domains_secondary TEXT,
    -- JSON array of secondary domains: '["devops", "ml"]'
    location TEXT,
    -- 'San Francisco, CA'
    description TEXT,
    -- Brief role description (optional, for context)
    display_order INTEGER,
    -- User-controlled ordering for resume display
    source_doc_id INTEGER REFERENCES uploaded_documents(id),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_roles_domain ON roles(domain);
CREATE INDEX idx_roles_type ON roles(type);
```

### 27.3 Updated KB Schema with Role Linkage

```sql
-- Modified knowledge_base table
CREATE TABLE knowledge_base (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    text TEXT NOT NULL,
    role_id INTEGER REFERENCES roles(id),
    -- ^^^ LINKS TO SPECIFIC ROLE — this is the provenance chain
    job_types TEXT,                 -- JSON: '["backend","devops"]'
    tags TEXT,                      -- JSON: '["python","aws"]'
    source_type TEXT,               -- 'llm_extraction', 'manual', 'import'
    source_doc_id INTEGER REFERENCES uploaded_documents(id),
    embedding BLOB,
    is_active INTEGER NOT NULL DEFAULT 1,
    effectiveness_score FLOAT DEFAULT 1.0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME,
    UNIQUE(category, text)
);
```

### 27.4 The Provenance Chain

Every bullet point has a clear lineage:

```
KB Entry #42: "Led migration to microservices, reducing deploy time by 60%"
  │
  ├─→ role_id: 7
  │     └─→ Role: "Senior Backend Engineer" at "Acme Corp"
  │         ├─→ start_date: "2020-06"
  │         ├─→ end_date: "2023-08"
  │         ├─→ domain: "backend"
  │         ├─→ domains_secondary: ["devops"]
  │         └─→ duration: 3 years 2 months
  │
  ├─→ source_doc_id: 3
  │     └─→ Document: "resume_2024.pdf" (uploaded 2026-03-10)
  │
  ├─→ category: "experience"
  ├─→ job_types: ["backend", "devops", "fullstack"]
  └─→ tags: ["microservices", "deployment", "architecture"]
```

### 27.5 Domain-Specific Experience Calculation

```python
# core/experience_calculator.py

def calculate_experience_by_domain(roles: list[Role]) -> dict[str, ExperienceDetail]:
    """Calculate years of experience per domain, handling overlaps and career changes.

    Returns dict keyed by domain with years, months, and role details.
    """
    domain_periods: dict[str, list[tuple[date, date]]] = defaultdict(list)

    for role in roles:
        start = parse_date(role.start_date)
        end = parse_date(role.end_date) if role.end_date else date.today()

        # Primary domain gets full credit
        domain_periods[role.domain].append((start, end))

        # Secondary domains get full credit too (you were using those skills)
        for secondary in json.loads(role.domains_secondary or "[]"):
            domain_periods[secondary].append((start, end))

    # Merge overlapping periods per domain
    result = {}
    for domain, periods in domain_periods.items():
        merged = _merge_overlapping_periods(periods)
        total_months = sum(
            (end.year - start.year) * 12 + (end.month - start.month)
            for start, end in merged
        )
        result[domain] = ExperienceDetail(
            years=total_months // 12,
            months=total_months % 12,
            total_months=total_months,
            roles=[r for r in roles if r.domain == domain
                   or domain in json.loads(r.domains_secondary or "[]")],
        )

    return result


def _merge_overlapping_periods(periods: list[tuple]) -> list[tuple]:
    """Merge overlapping date ranges (e.g., concurrent roles in same domain)."""
    if not periods:
        return []
    sorted_periods = sorted(periods, key=lambda p: p[0])
    merged = [sorted_periods[0]]
    for start, end in sorted_periods[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:  # overlap
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged


@dataclass
class ExperienceDetail:
    years: int
    months: int
    total_months: int
    roles: list  # Role objects contributing to this domain
```

### 27.6 Career Change Handling

A career changer's profile might look like:

```
Roles:
  1. High School Teacher — Lincoln High (2014-2019) [domain: teaching]
  2. Coding Bootcamp — App Academy (2019-2019) [domain: education]
  3. Junior Developer — StartupCo (2020-2021) [domain: fullstack]
  4. Backend Engineer — Acme Corp (2021-present) [domain: backend]

Experience Calculation:
  teaching:  5 years 0 months  (2014-2019)
  education: 0 years 6 months  (2019)
  fullstack: 1 year 0 months   (2020-2021)
  backend:   5 years 0 months  (2021-present, includes fullstack overlap)
  → Total "tech" experience: ~5 years (2020-present)
  → Backend-specific: ~4 years (2021-present)
```

### 27.7 JD Experience Requirement Matching

```python
def matches_experience_requirement(
    jd_analysis: JDAnalysis,
    experience_by_domain: dict[str, ExperienceDetail],
) -> ExperienceMatch:
    """Check if user's domain-specific experience meets JD requirements.

    Returns match result with details.
    """
    required_years = jd_analysis.experience_years  # e.g., 5
    detected_domain = jd_analysis.detected_domain   # e.g., "backend"

    if not required_years:
        return ExperienceMatch(meets=True, reason="No years requirement specified")

    # Check domain-specific experience first
    domain_exp = experience_by_domain.get(detected_domain)
    if domain_exp and domain_exp.total_months >= required_years * 12:
        return ExperienceMatch(
            meets=True,
            domain=detected_domain,
            years_have=domain_exp.years,
            years_need=required_years,
            reason=f"{domain_exp.years}+ years in {detected_domain} meets {required_years}+ requirement",
        )

    # Check related domains (e.g., "fullstack" counts partially for "backend")
    RELATED_DOMAINS = {
        "backend": ["fullstack", "devops", "data_engineer"],
        "frontend": ["fullstack", "mobile", "design"],
        "fullstack": ["backend", "frontend"],
        "devops": ["backend", "cloud", "sre"],
        "data_engineer": ["backend", "data_scientist", "ml_engineer"],
        "ml_engineer": ["data_scientist", "data_engineer", "backend"],
        "management": ["backend", "frontend", "fullstack"],  # tech leads count
    }

    related = RELATED_DOMAINS.get(detected_domain, [])
    combined_months = (domain_exp.total_months if domain_exp else 0)
    for rel_domain in related:
        rel_exp = experience_by_domain.get(rel_domain)
        if rel_exp:
            combined_months += rel_exp.total_months

    # Deduplicate overlapping periods across domains
    # (handled by merge_overlapping_periods on the raw role data)

    combined_years = combined_months // 12
    if combined_years >= required_years:
        return ExperienceMatch(
            meets=True,
            domain=detected_domain,
            years_have=combined_years,
            years_need=required_years,
            reason=f"{combined_years} years across {detected_domain} + related domains",
            includes_related=True,
        )

    return ExperienceMatch(
        meets=False,
        domain=detected_domain,
        years_have=combined_years,
        years_need=required_years,
        reason=f"Only {combined_years} years in {detected_domain} (need {required_years}+)",
        gap=required_years - combined_years,
    )
```

### 27.8 Role-Aware Resume Assembly

When assembling a resume, the role linkage ensures correctness:

```python
def assemble_resume(jd_text, kb, profile, roles, ...):
    """Assemble resume with proper role grouping and chronological ordering."""

    scored_entries = kb.score_against_jd(jd_text)

    # Group selected entries by role_id
    by_role: dict[int, list[ScoredEntry]] = defaultdict(list)
    for entry in scored_entries:
        if entry.category == "experience" and entry.role_id:
            by_role[entry.role_id].append(entry)

    # Build experience sections ordered by role date (most recent first)
    experience_sections = []
    for role_id, entries in sorted(
        by_role.items(),
        key=lambda x: roles_by_id[x[0]].start_date,
        reverse=True  # most recent first
    ):
        role = roles_by_id[role_id]

        # Format date range
        date_range = _format_date_range(role.start_date, role.end_date, role.is_current)

        experience_sections.append({
            "heading": f"{role.title} — {role.organization} ({date_range})",
            "bullets": [e.text for e in sorted(entries, key=lambda e: e.score, reverse=True)],
            "role": role,
        })

    # This guarantees:
    # 1. Bullets stay under their correct role/company/date
    # 2. Roles are in reverse chronological order
    # 3. No mixing of bullets between roles
    # 4. Date ranges are accurate (not estimated from subsection text)
```

### 27.9 Role Timeline UI

```
┌──────────────────────────────────────────────────────────────────┐
│  📋 Career Timeline                                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  2021 ──────────────── present                                    │
│  ████████████████████████████████  Backend Engineer — Acme Corp   │
│  domain: backend (+devops)         4 years 9 months               │
│  KB entries: 12 bullets            [Edit] [View Entries]          │
│                                                                   │
│  2020 ──── 2021                                                   │
│  ████████  Junior Developer — StartupCo                           │
│  domain: fullstack                 1 year 0 months                │
│  KB entries: 6 bullets             [Edit] [View Entries]          │
│                                                                   │
│  2019 ── 2019                                                     │
│  ████  App Academy (Bootcamp)                                     │
│  domain: education                 6 months                       │
│  KB entries: 2 bullets             [Edit] [View Entries]          │
│                                                                   │
│  2014 ──────────── 2019                                           │
│  ░░░░░░░░░░░░░░░░  High School Teacher — Lincoln High             │
│  domain: teaching                  5 years (non-tech)             │
│  KB entries: 3 bullets             [Edit] [View Entries]          │
│                                                                   │
│  ──────────────────────────────────────────────────────────────   │
│  Experience Summary:                                              │
│  • Backend:    4y 9m  (includes 1y fullstack overlap)             │
│  • Fullstack:  1y 0m                                              │
│  • DevOps:     4y 9m  (secondary domain from Acme)                │
│  • Teaching:   5y 0m  (non-tech, excluded from tech matching)     │
│  • Total tech: 5y 9m                                              │
│                                                                   │
│  [Add Role]  [Import from LinkedIn]                               │
└──────────────────────────────────────────────────────────────────┘
```

### 27.10 LLM Extraction Prompt Update

The extraction prompt (Section 2) must also extract role information:

```python
EXTRACTION_PROMPT = """
...existing instructions...

ADDITIONALLY, extract the employment/education timeline:
For each distinct role, project, or education entry, output a "role" object:
{
  "type": "employment" | "education" | "project" | "volunteer" | "freelance" | "certification",
  "title": "Senior Backend Engineer",
  "organization": "Acme Corp",
  "start_date": "2020-06",
  "end_date": "2023-08",       // null if current
  "is_current": false,
  "domain": "backend",          // primary domain
  "domains_secondary": ["devops"],
  "location": "San Francisco, CA"
}

Link each bullet point to its role by including a "role_ref" field:
{
  "category": "experience",
  "text": "Led migration to microservices...",
  "role_ref": "Senior Backend Engineer at Acme Corp",  // matches a role entry
  "job_types": ["backend", "devops"]
}

Output format:
{
  "roles": [...],
  "entries": [...]
}
"""
```

### 27.11 Domain Taxonomy

```python
DOMAIN_TAXONOMY = {
    # Tech domains
    "backend": {"label": "Backend Development", "color": "#3b82f6", "is_tech": True},
    "frontend": {"label": "Frontend Development", "color": "#8b5cf6", "is_tech": True},
    "fullstack": {"label": "Full-Stack Development", "color": "#6366f1", "is_tech": True},
    "mobile": {"label": "Mobile Development", "color": "#ec4899", "is_tech": True},
    "devops": {"label": "DevOps / SRE", "color": "#f59e0b", "is_tech": True},
    "cloud": {"label": "Cloud Architecture", "color": "#f97316", "is_tech": True},
    "data_engineer": {"label": "Data Engineering", "color": "#10b981", "is_tech": True},
    "data_scientist": {"label": "Data Science", "color": "#14b8a6", "is_tech": True},
    "ml_engineer": {"label": "ML Engineering", "color": "#06b6d4", "is_tech": True},
    "security": {"label": "Security Engineering", "color": "#ef4444", "is_tech": True},
    "qa": {"label": "QA / Testing", "color": "#84cc16", "is_tech": True},
    "embedded": {"label": "Embedded / Firmware", "color": "#78716c", "is_tech": True},
    "game_dev": {"label": "Game Development", "color": "#a855f7", "is_tech": True},

    # Non-tech domains (for career changers)
    "management": {"label": "Management", "color": "#64748b", "is_tech": False},
    "product": {"label": "Product Management", "color": "#0ea5e9", "is_tech": False},
    "design": {"label": "Design / UX", "color": "#d946ef", "is_tech": False},
    "teaching": {"label": "Teaching / Education", "color": "#a3a3a3", "is_tech": False},
    "sales": {"label": "Sales / Business Dev", "color": "#a3a3a3", "is_tech": False},
    "marketing": {"label": "Marketing", "color": "#a3a3a3", "is_tech": False},
    "finance": {"label": "Finance / Accounting", "color": "#a3a3a3", "is_tech": False},
    "healthcare": {"label": "Healthcare", "color": "#a3a3a3", "is_tech": False},
    "research": {"label": "Research / Academia", "color": "#a3a3a3", "is_tech": False},
    "other": {"label": "Other", "color": "#a3a3a3", "is_tech": False},
}
```

### 27.12 Impact on Existing Features

| Feature | How Role Linkage Improves It |
|---------|------|
| **Resume Assembly** | Bullets grouped under correct role/company/dates — never misplaced |
| **ATS Scoring (25.2)** | Experience years check uses domain-specific calculation, not total years |
| **One-Page Mode (23)** | Prioritize recent/relevant roles; can drop entire old roles to fit |
| **Resume Builder (24)** | Drag roles as groups, not individual bullets |
| **KB Health Check (21.2)** | Shows experience gaps per domain: "You have 0 DevOps entries" |
| **Interview Prep (26.2)** | Maps likely questions to specific roles: "Tell me about your time at Acme" |
| **Rejection Analysis (26.10)** | "You had 2y backend experience, role needed 5+ — that's likely why" |

---

## TODO: Details to Finalize

- [ ] LaTeX special character escaping (& % $ # _ { } ~ ^ \)
- [ ] ONNX model download UX (settings button vs auto-download)
- [ ] Cover letter knowledge base (separate KB or shared?)
- [ ] Export/import KB (backup, transfer between machines)
- [ ] Rate limiting on upload endpoint (prevent abuse)
- [ ] Max document size limit for uploads
- [ ] Supported languages for extraction (English only? multi-lingual?)
- [ ] KB entry versioning (track edits to entries)
- [ ] Bulk upload (multiple files at once)
- [ ] Preview debounce strategy (avoid excessive recompilation on rapid clicks)
- [ ] Preview caching (cache compiled PDF for same entry set + template combo?)
- [ ] Custom template upload/validation (user drops .tex.j2 into ~/.autoapply/templates/)
- [ ] Bot review mode integration (show preview before approve/skip decision)
