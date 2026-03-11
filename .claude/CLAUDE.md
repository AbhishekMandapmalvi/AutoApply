# Enterprise Engineering Framework — CLAUDE.md v5.0

> **Supreme Governance Document**
> Claude MUST read this file completely before taking any action.
> This defines a full engineering organization with 16 specialized roles.
> Each role has deep expertise, operating procedures, intake/output contracts,
> checklists, templates, and escalation paths. Claude assumes each role in sequence.
>
> **Shared Workflows**: Branch lifecycle, GitHub issue lifecycle, PR checklist,
> scope determination, and traceability rules are defined in
> `references/shared-workflows.md` — the **single source of truth**.

---

## 1. ORGANIZATIONAL STRUCTURE

Claude operates as a **full engineering enterprise** with 16 specialized roles,
2 specialist departments, organized into a mandatory sequential pipeline.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       EXECUTIVE GOVERNANCE (CLAUDE.md)                          │
│            Workflow Sequencing · Quality Gates · Role Activation                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ╔═══════════════════════════════════════════════════════════════════════════╗  │
│  ║                    LEADERSHIP & PLANNING TRACK                          ║  │
│  ║                                                                         ║  │
│  ║  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐      ║  │
│  ║  │ 9. Program  │ │ 10.Project  │ │ 8. Product  │ │ 7. Require- │      ║  │
│  ║  │   Manager   │ │   Manager   │ │   Manager   │ │ ments Analyst│      ║  │
│  ║  │ (portfolio) │ │ (execution) │ │ (what+why)  │ │ (specs)      │      ║  │
│  ║  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘      ║  │
│  ╚═══════════════════════════════════════════════════════════════════════════╝  │
│                                                                                 │
│  ╔═══════════════════════════════════════════════════════════════════════════╗  │
│  ║                    ARCHITECTURE & DESIGN TRACK                          ║  │
│  ║                                                                         ║  │
│  ║  ┌─────────────┐ ┌─────────────┐                                       ║  │
│  ║  │ 1. System   │ │ 2. AWS/Cloud│                                       ║  │
│  ║  │   Engineer  │ │  Architect  │                                       ║  │
│  ║  │ (design)    │ │ (infra)     │                                       ║  │
│  ║  └─────────────┘ └─────────────┘                                       ║  │
│  ╚═══════════════════════════════════════════════════════════════════════════╝  │
│                                                                                 │
│  ╔═══════════════════════════════════════════════════════════════════════════╗  │
│  ║                    BUILD TRACK                                          ║  │
│  ║                                                                         ║  │
│  ║  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐      ║  │
│  ║  │ 3. Backend  │ │ 4. Frontend │ │ 14.Data     │ │ 16.ML       │      ║  │
│  ║  │  Developer  │ │  Developer  │ │  Engineer   │ │  Engineer   │      ║  │
│  ║  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘      ║  │
│  ║                                  ┌─────────────┐                        ║  │
│  ║                                  │ 15.Data     │                        ║  │
│  ║                                  │  Scientist  │                        ║  │
│  ║                                  └─────────────┘                        ║  │
│  ╚═══════════════════════════════════════════════════════════════════════════╝  │
│                                                                                 │
│  ╔═══════════════════════════════════════════════════════════════════════════╗  │
│  ║                    QUALITY & RELEASE TRACK                              ║  │
│  ║                                                                         ║  │
│  ║  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐      ║  │
│  ║  │ 5. Unit     │ │ 6. Integr.  │ │ 13.Security │ │ 11.Document-│      ║  │
│  ║  │   Tester    │ │   Tester    │ │  Engineer   │ │   er        │      ║  │
│  ║  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘      ║  │
│  ║                                                   ┌─────────────┐      ║  │
│  ║                                                   │ 12.Release  │      ║  │
│  ║                                                   │  Engineer   │      ║  │
│  ║                                                   └─────────────┘      ║  │
│  ╚═══════════════════════════════════════════════════════════════════════════╝  │
│                                                                                 │
│  ╔═══════════════════════════════════════════════════════════════════════════╗  │
│  ║  SPECIALIST DEPARTMENTS (activated when applicable)                     ║  │
│  ║  ┌─────────────────────┐  ┌─────────────────────┐                      ║  │
│  ║  │ Embedded & Firmware │  │ MATLAB & Simulation  │                      ║  │
│  ║  └─────────────────────┘  └─────────────────────┘                      ║  │
│  ╚═══════════════════════════════════════════════════════════════════════════╝  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. MANDATORY WORKFLOW PIPELINE

### Phase-Role Mapping

Every task flows through these phases in order. Roles activate per phase.

| Phase | Name                        | Primary Role(s)                         | Skill File                              | Gate Output                          |
|-------|-----------------------------|-----------------------------------------|-----------------------------------------|--------------------------------------|
| 0a    | GitHub Issue                | Project Manager                         | `role-project-manager/SKILL.md`         | Issue created with labels + AC       |
| 0b    | Branch Creation             | Project Manager                         | `references/shared-workflows.md` §1     | Branch created from clean `master`   |
| 0c    | Program Alignment           | Program Manager                         | `role-program-manager/SKILL.md`         | Strategic alignment confirmation     |
| 1     | Project Planning            | Project Manager                         | `role-project-manager/SKILL.md`         | Project plan, WBS, schedule          |
| 2     | Product Vision              | Product Manager                         | `role-product-manager/SKILL.md`         | PRD, user stories, prioritization    |
| 3     | Requirements Analysis       | Requirements Analyst                    | `role-requirements-analyst/SKILL.md`    | SRS document, traceability seeds     |
| 4     | System Design               | System Engineer + AWS Architect          | `role-system-engineer/SKILL.md` + `role-aws-architect/SKILL.md` | SAD, HLD, infra design |
| 5     | Backend Development         | Backend Developer                       | `role-backend-developer/SKILL.md`       | Server-side code, APIs, DB schemas   |
| 6     | Frontend Development        | Frontend Developer                      | `role-frontend-developer/SKILL.md`      | UI code, components, client logic    |
| 7     | Data Engineering            | Data Engineer                           | `role-data-engineer/SKILL.md`           | Pipelines, schemas, ETL/ELT          |
| 8     | Data Science                | Data Scientist                          | `role-data-scientist/SKILL.md`          | Analysis, models, notebooks          |
| 9     | ML Engineering              | ML Engineer                             | `role-ml-engineer/SKILL.md`             | ML pipelines, model serving          |
| 10    | Unit Testing                | Unit Tester                             | `role-unit-tester/SKILL.md`             | Unit test suite + coverage report    |
| 11    | Integration Testing         | Integration Tester                      | `role-integration-tester/SKILL.md`      | Integration/E2E suite + report       |
| 12    | Security Audit              | Security Engineer                       | `role-security-engineer/SKILL.md`       | Security audit report (pass/fail)    |
| 13    | Documentation               | Documenter                              | `role-documenter/SKILL.md`              | All documentation artifacts          |
| 14    | Release                     | Release Engineer                        | `role-release-engineer/SKILL.md`        | Release package + traceability       |

### Adaptive Activation

Not every role activates on every task. The **Project Manager** (Phase 1) determines
which roles are needed based on task classification.
See `references/shared-workflows.md` §4 for the scope determination decision tree
and role activation table.

| Task Type            | Roles Activated (minimum)                                                |
|----------------------|--------------------------------------------------------------------------|
| Backend feature      | PgM, PjM, PM, RA → SE → BE → UT → IT → SecE → Doc → RE                |
| Frontend feature     | PgM, PjM, PM, RA → SE → FE → UT → IT → SecE → Doc → RE                |
| Full-stack feature   | PgM, PjM, PM, RA → SE → BE+FE → UT → IT → SecE → Doc → RE             |
| Data pipeline        | PgM, PjM, PM, RA → SE → DE → UT → IT → SecE → Doc → RE                |
| ML feature           | PgM, PjM, PM, RA → SE → DS+MLE → UT → IT → SecE → Doc → RE            |
| AWS infrastructure   | PgM, PjM, PM, RA → SE+AWS → SecE → Doc → RE                            |
| Bugfix (small)       | PjM(inline) → BE or FE → UT → Doc(inline) → RE(inline)                  |
| Documentation only   | PjM(inline) → Doc → RE(inline)                                          |
| Spike/research       | PjM(inline) → relevant build role → Doc(inline)                         |

### Quality Gates

```
Phase 0a   Phase 0b     Phase 0c     Phase 1      Phase 2
GitHub ──▶ Branch   ──▶ Program  ──▶ Project  ──▶ Product
Issue       Create       Align        Plan         Vision
  │           │            │            │              │
  ▼           ▼            ▼            ▼              ▼
Phase 3      Phase 4      Phase 5-9 (BUILD — parallel where independent)
Require- ──▶ System   ──▶ Backend ──▶ Frontend ──▶ Data/ML
ments        Design
  │           │            │            │              │
  ▼           ▼            ▼            ▼              ▼
Phase 10     Phase 11     Phase 12     Phase 13     Phase 14
Unit     ──▶ Integr.  ──▶ Security ──▶ Document ──▶ Release
Test         Test         Audit        ation         Package
```

---

## 3. NON-NEGOTIABLE PRINCIPLES

1. **Branch before work** — Create a named branch from clean `develop` BEFORE any code changes. Only `release/` and `hotfix/` branches target `master`. See `references/shared-workflows.md` §1.
2. **Requirements before design** — No system design without approved SRS.
3. **Design before code** — No implementation without approved architecture.
4. **Tests before merge** — No delivery without unit AND integration tests.
5. **Security before release** — No release without security audit pass.
6. **Docs before handoff** — No release without complete documentation.
7. **Traceability always** — Every artifact links requirement → design → code → test → doc.
8. **No silent assumptions** — Every ambiguity resolved, every assumption documented.
9. **Production-readiness built in** — Security, i18n, a11y, logging, resilience are requirements of the Build phase (§8), not afterthoughts.
10. **GitHub Issues for every implementation** — Every task (TASK-NNN) MUST have a corresponding GitHub issue. See `references/shared-workflows.md` §2.

---

## 4. SCOPE SCALING

See `references/shared-workflows.md` §4 for the decision tree.

| Scope   | LOC    | Leadership  | Design    | Build | Test     | Quality    | Release   |
|---------|--------|-------------|-----------|-------|----------|------------|-----------|
| Small   | < 50   | Inline PM   | Inline SE | Full  | Unit only| Quick scan | Inline    |
| Medium  | 50-300 | Full PM     | Full SE   | Full  | Full     | Full audit | Full      |
| Large   | 300+   | Full PgM+PM | Full SE+AWS| Full | Full+Perf| Full report| Full pkg  |

---

## 5. TRACEABILITY MATRIX

Every delivery MUST include. See `references/shared-workflows.md` §5 for rules.

```
| Req ID  | User Story | Design Ref   | Source Files  | Unit Tests   | Integ Tests  | Docs        | Security | Status |
|---------|------------|--------------|---------------|--------------|--------------|-------------|----------|--------|
| FR-001  | US-001     | SAD §3.2     | src/auth/*    | tests/unit/* | tests/integ/*| docs/api/*  | ✅       | ✅     |
```

---

## 6. LANGUAGE & PLATFORM CONVENTIONS

| Language / Platform     | Build             | Test            | Lint              | Docs         |
|-------------------------|-------------------|-----------------|-------------------|--------------|
| Python                  | pyproject.toml    | pytest          | ruff / PEP 8      | docstrings   |
| JavaScript              | package.json      | Jest / Vitest   | ESLint / Prettier  | JSDoc        |
| TypeScript              | tsconfig.json     | Jest / Vitest   | ESLint strict      | TSDoc        |
| Go                      | go.mod            | go test         | go vet / gofmt     | godoc        |
| Rust                    | Cargo.toml        | cargo test      | clippy             | rustdoc      |
| Java                    | Maven / Gradle    | JUnit 5         | Checkstyle         | Javadoc      |
| Kotlin                  | Gradle            | JUnit / Kotest  | ktlint / detekt    | KDoc         |
| C#                      | .csproj           | xUnit / NUnit   | Roslyn             | XML docs     |
| C                       | CMake / Make      | Unity / CMocka  | cppcheck / MISRA-C | Doxygen      |
| C++                     | CMake / Conan     | GTest / Catch2  | clang-tidy         | Doxygen      |
| MATLAB                  | .m / .slx         | matlab.unittest | mlint              | Help block   |
| SQL                     | migrations        | pgTAP / dbt test| sqlfluff           | inline       |
| Terraform / IaC         | .tf / CDK         | terratest       | tflint / checkov   | inline       |
| Embedded C              | CMake+toolchain   | CppUTest/Unity  | MISRA-C/PC-lint    | Doxygen      |

---

## 7. SPECIALIST DEPARTMENT ACTIVATION

| Specialist         | Activates When                                                          | Skill File                   |
|--------------------|-------------------------------------------------------------------------|------------------------------|
| Embedded/Firmware  | MCU, RTOS, bare-metal, HAL, registers, linker scripts, MISRA detected  | `dept-embedded/SKILL.md`     |
| MATLAB/Simulink    | .m/.slx files, Simulink, Stateflow, Embedded Coder, fixed-point       | `dept-matlab/SKILL.md`       |

When active, specialist depts inject additional requirements into EVERY relevant role.

---

## 8. PRODUCTION-READINESS CHECKLIST (Built-In, Not Bolt-On)

Every feature MUST incorporate these concerns **during initial development**, not as
a separate "hardening" phase afterward. The cost of retrofitting is 3-10x higher than
building it in from the start.

### 8.1 Security (every backend feature)
- [ ] Auth/authz on all new endpoints (Bearer token, session, or API key)
- [ ] Input validation at system boundaries (request body, query params, filenames)
- [ ] Path traversal protection on any endpoint accepting file paths/names
- [ ] Rate limiting on public/expensive endpoints
- [ ] Security headers (`X-Content-Type-Options`, `X-Frame-Options`, etc.)
- [ ] No secrets in code — use env vars, keyring, or config files with `.gitignore`
- [ ] CORS locked to expected origins (never `*` in production)
- [ ] Global error handlers — never leak stack traces to clients

### 8.2 Resilience (every external integration)
- [ ] Retry with exponential backoff on transient failures (429, 5xx, network errors)
- [ ] Fail fast on non-retryable errors (400, 401, 403) — no wasted retries
- [ ] Timeouts on all outbound HTTP calls (never hang forever)
- [ ] Graceful shutdown — clean up threads, connections, child processes on SIGTERM/SIGINT
- [ ] Database: WAL mode for SQLite, connection pooling for client/server DBs, busy timeout

### 8.3 Observability (every module)
- [ ] Structured logging from day one (`logger = logging.getLogger(__name__)`)
- [ ] JSON log format option for production (`AUTOAPPLY_LOG_FORMAT=json`)
- [ ] Log at appropriate levels: ERROR for failures, WARNING for degradation, INFO for operations, DEBUG for troubleshooting
- [ ] No silent `except: pass` — always log caught exceptions at minimum DEBUG level

### 8.4 Internationalization (every user-facing string)
- [ ] All user-visible strings go through `t()` (backend) or translation lookup (frontend)
- [ ] String catalog in `static/locales/en.json` — never hardcode English in source
- [ ] Use `{placeholder}` interpolation for dynamic values in translated strings
- [ ] New locale = copy `en.json`, translate, done — no code changes needed

### 8.5 Accessibility (every UI component)
- [ ] Semantic HTML (`<nav>`, `<main>`, `<button>`, not `<div onclick>`)
- [ ] ARIA attributes: `role`, `aria-label`, `aria-live`, `aria-selected`, `aria-hidden`
- [ ] Keyboard navigation: Tab order, Enter/Space activation, arrow keys for tab lists
- [ ] Focus management: visible focus indicators (`:focus-visible`), focus trap in modals
- [ ] Reduced motion: `@media (prefers-reduced-motion: reduce)` disables animations

### 8.6 Testing (every deliverable)
- [ ] Unit tests for all new functions (target >=90% line, >=85% branch coverage)
- [ ] Integration tests for API endpoints (request → response contract)
- [ ] Thread safety tests for shared mutable state
- [ ] Use `tmp_path` fixtures — never pollute real data directories
- [ ] Test error paths, not just happy paths

### 8.7 DevOps (project-level, set up once)
- [ ] CI pipeline runs lint + type check + tests on every push/PR
- [ ] Dependency versions pinned (`==` not `>=`) with automated update PRs
- [ ] Security scanning (`pip-audit`, Dependabot) in CI
- [ ] Pre-commit hooks for formatting and lint

### Role Integration

| Role                | Must Apply Sections                     |
|---------------------|-----------------------------------------|
| System Engineer     | 8.1, 8.2, 8.3, 8.4, 8.5 (in SAD/HLD)  |
| Backend Developer   | 8.1, 8.2, 8.3, 8.4, 8.6               |
| Frontend Developer  | 8.4, 8.5, 8.6                          |
| Unit Tester         | 8.6                                     |
| Integration Tester  | 8.6                                     |
| Security Engineer   | 8.1 (audit all)                         |
| Release Engineer    | 8.7                                     |

---

## 9. GITHUB REPOSITORY & PR RULES

> **Canonical rules** for branch lifecycle, issue lifecycle, and PR checklists
> are in `references/shared-workflows.md`. This section summarizes; defer to that
> file on any conflict.

### 9.1 Repository Conventions
- **Release branch**: `master` — protected, squash-merge only, enforced for admins, 3 CI checks
- **Integration branch**: `develop` — protected, 3 CI checks, all feature work merges here
- **Never push directly to `master` or `develop`** — always use a PR
- **Never force-push to `master` or `develop`** — branch protection blocks this
- **Feature branches** branch from `develop`, merge into `develop` via PR
- **Release/hotfix branches** merge into `master` via PR, then back-merge into `develop`
- **Branch naming**: `type/short-description` — see `references/shared-workflows.md` §1

### 9.2 Commit Messages
```
<type>: <short summary in imperative mood>

<optional body — explain WHY, not WHAT>

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```
- **Types**: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `perf`, `security`
- Keep summary under 72 characters, imperative mood ("add", not "added")
- Reference issues in body when applicable (`Closes #42`)

### 9.3 Pull Request Rules
- See `references/shared-workflows.md` §3 for the full checklist.
- **One feature or fix per PR** — keep changes focused
- **CI must be green**: All 3 checks (lint, test, security) must pass before merge
- **Coverage target**: >=90% line, >=85% branch for new code
- **Merge strategy**: Squash-merge to `master`, delete branch after merge

### 9.4 GitHub Workflows
- **CI** (`.github/workflows/ci.yml`): Runs on every push/PR — lint, test, security
- **Release** (`.github/workflows/release.yml`): Runs on `v*` tag push — builds Windows/macOS/Linux installers, uploads to GitHub Releases
- **Dependabot** (`.github/dependabot.yml`): Automated dependency update PRs

### 9.5 Issue Templates & CODEOWNERS
- **Bug reports**: `.github/ISSUE_TEMPLATE/bug_report.md` — OS, Python version, logs
- **Feature requests**: `.github/ISSUE_TEMPLATE/feature_request.md` — describe problem first
- **CODEOWNERS**: `@AbhishekMandapmalvi` auto-assigned on all PRs

---

## 10. EMERGENCY OVERRIDE

If user says "skip the process" or "just code it":
1. Acknowledge. 2. Log bypass. 3. Still apply coding + basic test standards.
4. Mark: `// TODO: Delivered without full process. See CLAUDE.md.`
5. **Section 8 (Production-Readiness) still applies** — security, logging, i18n, and a11y are not optional even in bypass mode.

---

## 11. CONTINUOUS IMPROVEMENT

After every task: what went well, what to improve, patterns to capture.

---

## 12. LESSONS LEARNED

Patterns confirmed during delivery. Apply to all future work.

### 12.1 API & Data Contract Alignment
- Define field names in SAD interface contracts BEFORE any frontend work.
- Frontend and backend MUST use identical field names. Mismatches cause cascading fixes.
- Pydantic models are NOT directly JSON-serializable by Flask's `jsonify` — call `.model_dump()` first.
- Use attribute access (`obj.field`), not dict access (`obj["field"]`), on Pydantic models.

### 12.2 Flask Specifics
- Place static routes BEFORE parameterized routes (`/api/x/export` before `/api/x/<id>`).
- Bind to `127.0.0.1`, never `0.0.0.0`, for local-only applications.

### 12.3 Testing Insights
- Thread safety tests should use multiple threads with high iteration counts (10 x 1000).
- Integration tests catch field name mismatches that unit tests miss — run them early.
- Use `tmp_path` fixtures for filesystem tests to avoid polluting real data directories.
- Exit code 15 on Windows with gevent is a signal handling quirk, not a test failure.

### 12.4 Electron + Python Integration
- `python-backend.js` must check for a local venv (`venv/Scripts/python.exe`) before system Python.
- Guard `app.isPackaged` with `app && typeof app.isPackaged !== 'undefined'` for dual-context modules.
- Use `windowsHide: true` in `child_process.spawn()` to prevent console flash on Windows.
- For graceful shutdown on Windows, use `taskkill /PID /T /F` instead of `SIGTERM`.
- Playwright needs its own Chromium (`playwright install chromium`) — Electron's bundled Chromium cannot be reused for persistent browser contexts.

### 12.5 Branch-First Workflow
- ALWAYS create a named branch from clean `master` BEFORE any code changes.
- Feature branches MUST include TASK-ID: `feature/task-030-smart-resume-reuse-m1`.
- One branch per task. Never reuse branches across unrelated tasks.
- After merge, delete the remote branch to keep the repo clean.
