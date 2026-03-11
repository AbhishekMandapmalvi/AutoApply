# Product Requirements Document

**Feature**: Smart Resume Reuse with Knowledge Base
**Date**: 2026-03-11
**Author**: Claude (Product Manager)
**Status**: approved
**Task ID**: TASK-030

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

### How is it solved today?
- LLM generates fresh resume per application (expensive, slow)
- Users manually write .txt experience files (unstructured, error-prone)
- Fallback templates used when no API key configured (poor quality)

---

## 2. User Personas

| Persona | Description | Key Need | Pain Point | Frequency |
|---------|-------------|----------|------------|-----------|
| Active Seeker | Job seeker running bot daily, 20-50 apps/day | Reduce API costs while maintaining quality | $10+/day in API calls, slow generation | Daily |
| Career Switcher | Professional with diverse experience | Relevant resume for each job type | Manual .txt files don't adapt well | Weekly |
| Power User | Technical user who wants control | Fine-tune which bullets appear on resume | No visibility into what LLM selects | Ongoing |

---

## 3. User Stories

| ID | As a... | I want to... | So that... | Priority | Size |
|----|---------|-------------|------------|----------|------|
| US-101 | Active Seeker | upload my career documents once and have them processed into reusable entries | I don't pay for LLM extraction per application | P0 | L |
| US-102 | Active Seeker | have the system automatically select relevant entries for each job | resumes are tailored without API calls | P0 | L |
| US-103 | Power User | view and edit my knowledge base entries | I can correct or improve extracted content | P0 | M |
| US-104 | Career Switcher | have entries tagged by job type | only relevant experience appears for each role | P1 | M |
| US-105 | Active Seeker | have LLM-generated resumes automatically ingested into KB | the system improves with every application | P1 | S |
| US-106 | Power User | configure scoring thresholds and template settings | I control resume quality vs. cost tradeoff | P2 | S |

### Acceptance Criteria

#### US-101: Document Upload & Extraction
- Given a PDF/DOCX/TXT/MD file, When uploaded, Then text is extracted and sent to LLM once
- Given LLM response, When parsed, Then categorized entries are stored in KB with dedup

#### US-102: Automatic Resume Assembly
- Given a JD and populated KB, When bot generates docs, Then KB assembly is tried first
- Given insufficient KB entries, When assembly fails, Then system falls through to LLM generation

#### US-103: KB Viewer & Editor
- Given KB entries exist, When user opens KB viewer, Then all entries shown with category/text/tags
- Given an entry, When user edits text or tags, Then changes are persisted immediately

---

## 4. Success Metrics

| Metric | Current Baseline | Target | Measurement Method | Timeline |
|--------|-----------------|--------|-------------------|----------|
| API calls per application | 2 (resume + CL) | 0-1 (CL only or none) | Count invoke_llm calls | After M4 |
| Resume generation latency | 10-30s | <500ms (KB assembly) | Time _generate_docs() | After M4 |
| KB entry count after 1 week | 0 | 50+ entries | DB query | After M1 upload |

---

## 5. Scope

### In Scope (M1 — Foundation)
- DB schema for KB, uploaded documents, roles tables
- Document text extraction (PDF, DOCX, TXT, MD)
- LLM-based extraction prompt and parsing
- KB CRUD operations with dedup
- Resume markdown parser for ingestion
- Experience calculator from roles
- Config models (ResumeReuseConfig, LatexConfig)
- i18n keys for KB UI (future milestones)

### Out of Scope (M1)
- TF-IDF scoring engine (M2)
- LaTeX compilation (M3)
- Bot integration (M4)
- Frontend UI (M5)
- ATS scoring (M6)
- Manual builder (M7)
- Performance optimizations (M8)
- Intelligence features (M9)
- Migration (M10)

---

## 6. Prioritization (MoSCoW for M1)

- **Must have**: DB schema, document parser, KB CRUD, config models (60%)
- **Should have**: LLM extraction, resume parser, experience calculator (30%)
- **Could have**: i18n keys pre-populated for future UI (10%)
- **Won't have**: Frontend, scoring, LaTeX, bot integration (M2+)

---

## 7. Constraints
- Must use SQLite (existing DB layer, no new infrastructure)
- Must maintain backward compatibility with existing config.json
- LLM extraction must work with all 4 supported providers
- New dependencies must be pinned versions

## 8. Risks
| Risk | Probability | Impact | Mitigation |
|------|:-----------:|:------:|-----------|
| LLM extraction produces bad JSON | M | M | Robust parsing with fallback, validation |
| PyPDF2 can't extract from scanned PDFs | M | L | Log warning, user can re-upload as TXT |
| Dedup too aggressive (different contexts) | L | M | Dedup on (category, text) — subsection differs OK |

## 9. Open Questions
| # | Question | Needed By | Status |
|---|---------|-----------|--------|
| 1 | ONNX embedding model size acceptable for distribution? | M2 | open |
| 2 | TinyTeX bundle size for Electron packaging? | M3 | open |
