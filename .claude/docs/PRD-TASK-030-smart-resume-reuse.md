# Product Requirements Document

**Feature**: Smart Resume Reuse with Knowledge Base
**Date**: 2026-03-11
**Updated**: 2026-03-12
**Author**: Claude (Product Manager)
**Status**: approved — all 10 milestones delivered
**Task ID**: TASK-030
**Version Target**: v2.3.0

---

## 1. Problem Statement

### What problem are we solving?
Every job application currently costs 2 cloud LLM API calls (resume + cover letter). For users applying to 50+ similar roles, this is expensive (~$0.10-0.50/application) and redundant — the same experience bullets get regenerated from scratch each time.

### Who has this problem?
Job seekers using AutoApply in automated mode who apply to many similar positions (e.g., 20 "Backend Engineer" roles in one week).

### How big is this problem?
- At 50 applications/day × $0.20/app = $10/day = $300/month in API costs
- Each generation takes 10-30s latency, slowing the bot loop
- Users must manually maintain .txt experience files with no structure
- No way to learn which resume content leads to interviews

### How is it solved today?
- LLM generates fresh resume per application (expensive, slow)
- Users manually write .txt experience files (unstructured, error-prone)
- Fallback templates used when no API key configured (poor quality)
- No feedback loop — system doesn't learn from outcomes

---

## 2. User Personas

| Persona | Description | Key Need | Pain Point | Frequency |
|---------|-------------|----------|------------|-----------|
| Active Seeker | Job seeker running bot daily, 20-50 apps/day | Reduce API costs while maintaining quality | $10+/day in API calls, slow generation | Daily |
| Career Switcher | Professional with diverse experience | Relevant resume for each job type | Manual .txt files don't adapt well | Weekly |
| Power User | Technical user who wants control | Fine-tune which bullets appear on resume | No visibility into what LLM selects | Ongoing |
| New User | First-time AutoApply user with existing resume files | Seamless onboarding without manual data entry | Existing .txt/.md files not automatically imported | One-time |

---

## 3. User Stories

### M1 — Foundation

| ID | As a... | I want to... | So that... | Priority | Size | Milestone |
|----|---------|-------------|------------|----------|------|-----------|
| US-101 | Active Seeker | upload my career documents once and have them processed into reusable entries | I don't pay for LLM extraction per application | P0 | L | M1 |
| US-102 | Power User | have extracted entries categorized (experience, skill, education, certification) | I can manage my KB by section | P0 | M | M1 |
| US-103 | Active Seeker | have duplicate entries automatically detected and skipped | my KB stays clean without manual curation | P1 | S | M1 |
| US-104 | Power User | configure resume reuse thresholds and template preferences | I control resume quality vs. cost tradeoff | P2 | S | M1 |

### M2 — Scoring

| ID | As a... | I want to... | So that... | Priority | Size | Milestone |
|----|---------|-------------|------------|----------|------|-----------|
| US-105 | Active Seeker | have KB entries automatically ranked by relevance to each job description | the most relevant experience appears on my resume | P0 | L | M2 |
| US-106 | Career Switcher | have the system understand that "Python" and "python3" are the same skill | scoring doesn't miss matches due to naming variations | P1 | M | M2 |
| US-107 | Power User | have optional ONNX-based semantic matching for deeper relevance | scoring goes beyond keyword matching when available | P2 | S | M2 |

### M3 — LaTeX Engine

| ID | As a... | I want to... | So that... | Priority | Size | Milestone |
|----|---------|-------------|------------|----------|------|-----------|
| US-108 | Active Seeker | have resumes compiled as pixel-perfect PDFs via LaTeX | my resumes look professional and pass ATS parsing | P0 | L | M3 |
| US-109 | Power User | choose from multiple resume templates (classic, modern, academic, minimal) | I can match the style to the industry/company | P1 | M | M3 |
| US-110 | Active Seeker | have special characters (%, $, &, \) properly escaped in LaTeX | my resume compiles without errors regardless of content | P0 | S | M3 |

### M4 — Assembly + Bot Integration

| ID | As a... | I want to... | So that... | Priority | Size | Milestone |
|----|---------|-------------|------------|----------|------|-----------|
| US-111 | Active Seeker | have the bot try KB assembly first before calling the LLM | I save API costs on every application where KB is sufficient | P0 | L | M4 |
| US-112 | Active Seeker | have LLM-generated resumes automatically ingested back into KB | the system improves with every application | P1 | M | M4 |
| US-113 | Power User | see whether each resume was KB-assembled or LLM-generated | I can track the system's self-sufficiency over time | P2 | S | M4 |

### M5 — Upload UI + KB Viewer

| ID | As a... | I want to... | So that... | Priority | Size | Milestone |
|----|---------|-------------|------------|----------|------|-----------|
| US-114 | Active Seeker | upload documents through a drag-and-drop UI | I can populate my KB without CLI commands | P0 | M | M5 |
| US-115 | Power User | view and edit my knowledge base entries in a table | I can correct or improve extracted content | P0 | M | M5 |
| US-116 | Power User | search and filter KB entries by category and keywords | I can find specific entries quickly | P1 | S | M5 |
| US-117 | Active Seeker | preview how my resume would look with current KB entries | I can verify quality before the bot uses it | P1 | M | M5 |

### M6 — ATS Scoring

| ID | As a... | I want to... | So that... | Priority | Size | Milestone |
|----|---------|-------------|------------|----------|------|-----------|
| US-118 | Active Seeker | see an ATS compatibility score for my resume against a JD | I know if my resume will pass automated screening | P0 | M | M6 |
| US-119 | Career Switcher | see which keywords and skills are missing from my resume | I can add relevant entries to improve my score | P0 | M | M6 |
| US-120 | Power User | see how scoring differs across ATS platforms (Greenhouse, Lever, Workday) | I can optimize for the specific platform each company uses | P1 | S | M6 |

### M7 — Manual Resume Builder

| ID | As a... | I want to... | So that... | Priority | Size | Milestone |
|----|---------|-------------|------------|----------|------|-----------|
| US-121 | Power User | manually drag-and-drop KB entries to build a custom resume | I have full control over exactly which bullets appear | P0 | L | M7 |
| US-122 | Power User | save and load named resume presets | I can quickly switch between configurations for different role types | P1 | M | M7 |
| US-123 | Active Seeker | see a one-page indicator while building | I know when my resume exceeds one page | P1 | S | M7 |
| US-124 | Career Switcher | auto-fill entries from a JD using keyword matching | I get a starting point without manually selecting each entry | P1 | M | M7 |

### M8 — Performance

| ID | As a... | I want to... | So that... | Priority | Size | Milestone |
|----|---------|-------------|------------|----------|------|-----------|
| US-125 | Active Seeker | have compiled PDFs cached so identical resumes aren't recompiled | resume generation is instant for repeat content | P1 | M | M8 |
| US-126 | Career Switcher | have KB entries pre-filtered by job type before scoring | scoring is faster and more relevant for my target role | P1 | M | M8 |
| US-127 | Active Seeker | upload documents asynchronously without blocking the UI | I can continue using the app while files are processing | P1 | S | M8 |

### M9 — Intelligence

| ID | As a... | I want to... | So that... | Priority | Size | Milestone |
|----|---------|-------------|------------|----------|------|-----------|
| US-128 | Active Seeker | provide interview/rejection feedback to improve future scoring | entries that lead to interviews are prioritized | P1 | M | M9 |
| US-129 | Active Seeker | have cover letters assembled from KB entries without LLM calls | I save API costs on cover letters too | P1 | M | M9 |
| US-130 | Power User | see reuse analytics (total assemblies, interview rate, top entries) | I understand how well the KB system is working | P2 | S | M9 |
| US-131 | Active Seeker | have effectiveness scores blended into TF-IDF ranking | proven entries rank higher automatically over time | P1 | S | M9 |

### M10 — Migration + Polish

| ID | As a... | I want to... | So that... | Priority | Size | Milestone |
|----|---------|-------------|------------|----------|------|-----------|
| US-132 | New User | have my existing .txt experience files auto-migrated into KB on first startup | I don't need to re-upload content I already have | P0 | M | M10 |
| US-133 | New User | have my existing .md resume files auto-migrated into KB | previously generated resumes feed the KB immediately | P1 | M | M10 |
| US-134 | Active Seeker | have LaTeX handle backslashes in my content without breaking compilation | resumes with file paths or special content compile correctly | P0 | S | M10 |

### Acceptance Criteria

#### US-101: Document Upload & Extraction (M1)
- Given a PDF/DOCX/TXT/MD file, When uploaded, Then text is extracted and sent to LLM once
- Given LLM response, When parsed, Then categorized entries are stored in KB with dedup

#### US-105: Automatic Scoring (M2)
- Given a JD and KB entries, When scored, Then entries ranked by TF-IDF cosine similarity
- Given synonym aliases exist, When "python3" appears in JD, Then "Python" entries score higher

#### US-108: LaTeX Compilation (M3)
- Given rendered LaTeX content, When compiled, Then a valid PDF is produced
- Given pdflatex is not installed, When compilation attempted, Then ReportLab fallback is used

#### US-111: KB-First Bot Flow (M4)
- Given a JD and populated KB, When bot generates docs, Then KB assembly is tried first
- Given insufficient KB entries, When assembly fails, Then system falls through to LLM generation
- Given LLM generates a resume, When generation completes, Then output is ingested into KB

#### US-115: KB Viewer & Editor (M5)
- Given KB entries exist, When user opens KB viewer, Then all entries shown with category/text/tags
- Given an entry, When user edits text or tags, Then changes are persisted immediately

#### US-118: ATS Compatibility (M6)
- Given a JD and KB entries, When ATS score requested, Then composite score (0-100) returned
- Given missing keywords, When gap analysis run, Then missing keywords/skills/sections listed

#### US-121: Manual Builder (M7)
- Given KB entries displayed, When user drags entry to resume section, Then entry appears in that section
- Given a built resume, When user clicks save preset, Then preset saved with name and entry IDs

#### US-125: PDF Cache (M8)
- Given identical LaTeX content, When compiled twice, Then second compile returns cached PDF
- Given cache exceeds 200 entries, When new entry added, Then oldest entry evicted (LRU)

#### US-128: Outcome Feedback (M9)
- Given an application, When user provides "interview" outcome, Then effectiveness_score recalculated
- Given entries with high effectiveness, When scoring, Then TF-IDF blended with effectiveness (70/30)

#### US-132: Auto-Migration (M10)
- Given .txt files in profile/experiences/, When first startup, Then lines parsed as KB entries
- Given migration already completed, When startup, Then migration skipped (marker file check)

---

## 4. Success Metrics

| Metric | Current Baseline | Target | Measurement Method | Timeline |
|--------|-----------------|--------|-------------------|----------|
| API calls per application | 2 (resume + CL) | 0 (both from KB) | Count invoke_llm calls | After M9 |
| Resume generation latency | 10-30s | <500ms (KB assembly) | Time _generate_docs() | After M4 |
| KB entry count after 1 week | 0 | 50+ entries | DB query | After M1 upload |
| ATS pass rate | Unknown | 80%+ score on generated resumes | ATS scorer composite | After M6 |
| Interview rate from KB resumes | N/A | Track and improve | effectiveness_score | After M9 |
| Legacy file migration | Manual setup | 100% auto-migration | run_migration() count | After M10 |

---

## 5. Scope

### Full Feature Scope (M1–M10)

| Milestone | Scope | Status |
|-----------|-------|--------|
| M1 — Foundation | DB schema, document parser, KB CRUD, LLM extraction, resume parser, experience calculator, config models | Delivered (PR #39) |
| M2 — Scoring | TF-IDF cosine similarity, JD analyzer (keywords, n-grams, synonyms), ONNX embedding interface | Delivered (PR #45) |
| M3 — LaTeX Engine | pdflatex discovery, 4 Jinja2 templates, special char escaping, TinyTeX bundler | Delivered (PR #47) |
| M4 — Assembly + Bot | Resume assembler (score→select→render→compile), KB-first bot flow, post-LLM ingestion, version tracking | Delivered (PR #49) |
| M5 — Upload UI | 8 REST endpoints, KB viewer/editor, upload zone, resume preview modal, template picker | Delivered (PR #51) |
| M6 — ATS Scoring | 5-component composite scorer, 7 ATS platform profiles, keyword gap analysis | Delivered (PR #53) |
| M7 — Manual Builder | Drag-and-drop builder, resume presets CRUD, one-page mode, auto-fill from JD | Delivered (PR #54) |
| M8 — Performance | PDF compilation cache (SHA256 LRU), JD classifier (9 job types), async document upload | Delivered (PR #55) |
| M9 — Intelligence | Outcome-based learning, cover letter KB assembly, effectiveness weighting, reuse stats | Delivered (PR #56) |
| M10 — Migration | Auto-migrate .txt/.md files, LaTeX backslash hardening, category guessing heuristics | Delivered (PR #57) |

### Out of Scope
- OCR for scanned PDF images (user can re-upload as TXT)
- Multi-user / cloud deployment (desktop app only)
- Resume formatting beyond 4 LaTeX templates
- Cover letter LaTeX templates (CL uses text-only assembly)

---

## 6. Prioritization (MoSCoW — Full Feature)

- **Must have** (P0, 60%): Document upload + extraction, KB CRUD, TF-IDF scoring, LaTeX compilation, KB-first bot flow, KB viewer UI, ATS scoring, auto-migration — *the core value proposition*
- **Should have** (P1, 30%): Manual builder, presets, PDF cache, JD classifier, outcome learning, effectiveness weighting, cover letter assembly — *significant quality-of-life improvements*
- **Could have** (P2, 10%): ONNX embeddings, reuse stats analytics, config fine-tuning — *nice-to-have for power users*
- **Won't have**: Cloud sync, multi-user, OCR, custom template editor — *future features*

---

## 7. Constraints
- Must use SQLite (existing DB layer, no new infrastructure)
- Must maintain backward compatibility with existing config.json
- LLM extraction must work with all 4 supported providers (Anthropic, OpenAI, Google, DeepSeek)
- New dependencies must be pinned versions
- LaTeX compilation must fall back to ReportLab when pdflatex unavailable
- All user-facing strings must go through i18n (t() backend, data-i18n frontend)
- All UI components must meet WCAG 2.1 AA accessibility

## 8. Risks

| Risk | Probability | Impact | Mitigation | Status |
|------|:-----------:|:------:|-----------|--------|
| LLM extraction produces bad JSON | M | M | Robust parsing with fallback, validation | Resolved — json.loads with fence stripping |
| PyPDF2 can't extract from scanned PDFs | M | L | Log warning, user can re-upload as TXT | Accepted |
| Dedup too aggressive (different contexts) | L | M | Dedup on (category, text) — subsection differs OK | Resolved |
| TF-IDF misses semantic similarity | M | M | ONNX embedding blending (optional), synonym normalization | Mitigated — synonym map + tech terms |
| LaTeX compilation fails on edge cases | L | M | ReportLab fallback, escape_latex() for 10 special chars | Resolved — placeholder technique for backslash |
| KB pollution from low-quality LLM output | L | M | Dedup constraint, min_score threshold during assembly | Mitigated |
| Async upload thread leaks | L | H | Daemon threads, threading.Lock, finally cleanup | Resolved |

## 9. Open Questions

| # | Question | Needed By | Status |
|---|---------|-----------|--------|
| 1 | ONNX embedding model size acceptable for distribution? | M2 | Resolved — ONNX is optional, TF-IDF is default. Stub interface ready for future implementation. |
| 2 | TinyTeX bundle size for Electron packaging? | M3 | Resolved — bundle-tinytex.js downloads platform-specific minimal install (~100MB). Not included in base package. |
| 3 | Should effectiveness_score decay over time? | M9 | Open — currently uses all-time ratio. Could add recency weighting in future. |

---

## 10. Milestone-to-User-Story Mapping

| Milestone | User Stories | Issues | PR |
|-----------|-------------|--------|-----|
| M1 — Foundation | US-101, US-102, US-103, US-104 | #35, #36, #37, #38 | #39 |
| M2 — Scoring | US-105, US-106, US-107 | #44 | #45 |
| M3 — LaTeX Engine | US-108, US-109, US-110 | #46 | #47 |
| M4 — Assembly + Bot | US-111, US-112, US-113 | #48 | #49 |
| M5 — Upload UI | US-114, US-115, US-116, US-117 | #50 | #51 |
| M6 — ATS Scoring | US-118, US-119, US-120 | #52 | #53 |
| M7 — Manual Builder | US-121, US-122, US-123, US-124 | #58 | #54 |
| M8 — Performance | US-125, US-126, US-127 | #59 | #55 |
| M9 — Intelligence | US-128, US-129, US-130, US-131 | #60 | #56 |
| M10 — Migration | US-132, US-133, US-134 | #61 | #57 |

**Total**: 34 user stories across 10 milestones, 3 personas, all delivered.

---

## Product Requirements Document -- GATE 2 OUTPUT

**Document**: PRD-TASK-030-smart-resume-reuse
**User Stories**: 34 (US-101 to US-134)
**Personas**: 4 (Active Seeker, Career Switcher, Power User, New User)
**Success Metrics**: 6 measurable outcomes
**MoSCoW**: P0 (60%), P1 (30%), P2 (10%)
**Risks**: 7 identified, 5 resolved, 1 accepted, 1 mitigated
**Open Questions**: 2 resolved, 1 open (non-blocking)

### Handoff Routing
| Recipient | What They Receive |
|-----------|-------------------|
| Requirements Analyst | User stories + ACs for SRS elaboration |
| System Engineer | Scope + constraints for architecture design |
| Unit Tester | Acceptance criteria for test case generation |
