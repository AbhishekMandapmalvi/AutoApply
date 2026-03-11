# Enterprise Engineering Framework — CLAUDE.md v4.2

> **Supreme Governance Document**
> Claude MUST read this file completely before taking any action.
> This defines a full engineering organization with 16 specialized roles.
> Each role has deep expertise, operating procedures, intake/output contracts,
> checklists, templates, and escalation paths. Claude assumes each role in sequence.

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
| 0     | Program Alignment           | Program Manager                         | `role-program-manager/SKILL.md`         | Strategic alignment confirmation     |
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
which roles are needed based on task classification:

| Task Type            | Roles Activated (minimum)                                                |
|----------------------|--------------------------------------------------------------------------|
| Backend feature      | 7,8,9,10 → 1 → 3 → 4 → 5 → 10 → 11 → 13 → 12 → 14                    |
| Frontend feature     | 7,8,9,10 → 1 → 3 → 4 → 6 → 10 → 11 → 13 → 12 → 14                    |
| Full-stack feature   | 7,8,9,10 → 1 → 3 → 4 → 5+6 → 10 → 11 → 13 → 12 → 14                  |
| Data pipeline        | 7,8,9,10 → 1 → 3 → 4 → 7 → 10 → 11 → 13 → 12 → 14                    |
| ML feature           | 7,8,9,10 → 1 → 3 → 4 → 8+9 → 10 → 11 → 13 → 12 → 14                  |
| AWS infrastructure   | 7,8,9,10 → 1 → 3 → 2+4 → 13 → 12 → 14                                 |
| Bugfix (small)       | 10 → 3(inline) → 5 or 6 → 10 → 13(inline) → 12(inline)                 |
| Documentation only   | 10 → 13 → 14(inline)                                                    |
| Spike/research       | 10 → 3(inline) → relevant build role → 13(inline)                       |

Legend: Numbers reference role numbers from the org chart.

### Quality Gates

```
Phase 0    Phase 1      Phase 2      Phase 3       Phase 4
Program ──▶ Project ──▶ Product  ──▶ Require-  ──▶ System
Align       Plan         Vision       ments         Design
  │           │            │            │              │
  ▼           ▼            ▼            ▼              ▼
Phase 5-9 (BUILD — parallel where independent)
Backend ──▶ Frontend ──▶ Data Eng ──▶ Data Sci ──▶ ML Eng
  │           │            │            │              │
  ▼           ▼            ▼            ▼              ▼
Phase 10     Phase 11     Phase 12     Phase 13     Phase 14
Unit     ──▶ Integr.  ──▶ Security ──▶ Document ──▶ Release
Test         Test         Audit        ation         Package
```

---

## 3. NON-NEGOTIABLE PRINCIPLES

1. **Requirements before design** — No system design without approved SRS.
2. **Design before code** — No implementation without approved architecture.
3. **Tests before merge** — No delivery without unit AND integration tests.
4. **Security before release** — No release without security audit pass.
5. **Docs before handoff** — No release without complete documentation.
6. **Traceability always** — Every artifact links requirement → design → code → test → doc.
7. **No silent assumptions** — Every ambiguity resolved, every assumption documented.
8. **Production-readiness built in** — Security, i18n, a11y, logging, resilience are requirements of the Build phase (§8), not afterthoughts. Every new endpoint uses `t()`, every new UI element has ARIA, every external call has retry+timeout.
9. **GitHub Issues for every implementation** — Every task (TASK-NNN) MUST have a corresponding GitHub issue. Create the issue at the START of implementation (Phase 1/2), update it during build with progress notes, and close it with a completion comment referencing the commit hash when pushed. Use `gh issue create` and `gh issue close` via CLI.

---

## 4. SCOPE SCALING

| Scope   | LOC    | Leadership  | Design    | Build | Test     | Quality    | Release   |
|---------|--------|-------------|-----------|-------|----------|------------|-----------|
| Small   | < 50   | Inline PM   | Inline SE | Full  | Unit only| Quick scan | Inline    |
| Medium  | 50-300 | Full PM     | Full SE   | Full  | Full     | Full audit | Full      |
| Large   | 300+   | Full PgM+PM | Full SE+AWS| Full | Full+Perf| Full report| Full pkg  |

---

## 5. TRACEABILITY MATRIX

Every delivery MUST include:

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
- [ ] Unit tests for all new functions (target >80% line coverage)
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

### 9.1 Repository Conventions
- **Main branch**: `master` — protected with 3 required CI checks (lint, test, security)
- **Never push directly to `master`** — always use a PR
- **Never force-push to `master`** — branch protection blocks this
- **Branch naming**: `type/short-description` (e.g., `feature/locale-switcher`, `fix/login-timeout`)
  - Types: `feature/`, `fix/`, `refactor/`, `docs/`, `test/`, `chore/`
- **Mandatory branch creation**: Before ANY code change (feature, bugfix, refactor, etc.), Claude
  MUST create a new branch from `master` using the naming convention above. No work on `master`.
  - Features: `feature/{task-id}-{short-name}` (e.g., `feature/task-030-smart-resume-reuse-m1`)
  - Bugfixes: `fix/{issue-or-description}` (e.g., `fix/mypy-type-error-experience-calc`)
  - Refactors: `refactor/{short-name}` (e.g., `refactor/extract-db-helpers`)
  - Docs: `docs/{short-name}` (e.g., `docs/update-readme-test-count`)
  - Tests: `test/{short-name}` (e.g., `test/add-kb-integration-tests`)
  - Chores: `chore/{short-name}` (e.g., `chore/update-dependencies`)
- **Branch lifecycle**: Create branch → commit changes → push → open PR → CI green → squash-merge → delete branch
- **One branch per task**: Each TASK-NNN or bugfix gets its own branch. Never reuse branches across unrelated tasks.

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
- **One feature or fix per PR** — keep changes focused
- **Title**: Under 72 characters, describes the change
- **Description**: Must include Summary, Changes, Test plan (use PR template)
- **CI must be green**: All 3 checks (lint, test, security) must pass before merge
- **Branch must be current** with `master` before merge
- **Tests required**: New code must have corresponding tests
- **No secrets**: Never commit API keys, tokens, `.env`, or `config.json` with real data
- **Review**: Address all review feedback with new commits (don't force-push during review)
- **Merge strategy**: Squash-merge to `master`

### 9.4 PR Size Guidelines
| Size   | LOC Changed | Expectation |
|--------|-------------|-------------|
| Small  | < 50        | Quick review, merge same day |
| Medium | 50–300      | Detailed review, may need revisions |
| Large  | 300+        | Break into smaller PRs when possible |

### 9.5 Before Opening a PR
1. **Branch** (must be done FIRST, before any code changes):
   - `git checkout master && git pull origin master`
   - `git checkout -b type/short-description` (see §9.1 naming convention)
2. Run locally: `ruff check .` (lint) + `mypy` (type check) + `python -m pytest tests/ -v` (tests)
3. Update `CHANGELOG.md` under `[Unreleased]` if user-facing
4. Update `docs/` and `README.md` if features/test count changed

### 9.6 GitHub Workflows
- **CI** (`.github/workflows/ci.yml`): Runs on every push/PR — lint, test, security
- **Release** (`.github/workflows/release.yml`): Runs on `v*` tag push — builds Windows/macOS/Linux installers, uploads to GitHub Releases
- **Dependabot** (`.github/dependabot.yml`): Automated dependency update PRs

### 9.7 Issue Templates
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

### 12.1 API Contract Alignment
- Define field names in SAD interface contracts BEFORE any frontend work.
- Frontend and backend MUST use identical field names (e.g., `full_name` not `name`,
  `search_criteria` not `preferences`). Mismatches cause cascading fixes.
- Run a contract check between SAD field names and frontend code before integration.

### 12.2 Flask Route Ordering
- Place static routes BEFORE parameterized routes (`/api/x/export` before `/api/x/<id>`).
- Flask matches routes top-down; a parameterized route can shadow a static sibling.

### 12.3 Pydantic Model Serialization
- Pydantic models are NOT directly JSON-serializable by Flask's `jsonify`.
- Always call `.model_dump()` before passing to `jsonify`.
- Use attribute access (`obj.field`), not dict access (`obj["field"]`), on Pydantic models.

### 12.4 Security Checks During Build
- Add path traversal protection (allowlist regex) on ANY endpoint accepting filenames.
- Add global error handlers early — unhandled exceptions leak stack traces as HTML.
- Bind to `127.0.0.1`, never `0.0.0.0`, for local-only applications.

### 12.5 Testing Insights
- Thread safety tests should use multiple threads with high iteration counts (10 x 1000).
- Integration tests catch field name mismatches that unit tests miss — run them early.
- Use `tmp_path` fixtures for filesystem tests to avoid polluting real data directories.
- Exit code 15 on Windows with gevent is a signal handling quirk, not a test failure.

### 12.6 Electron + Python Integration
- `python-backend.js` must check for a local venv (`venv/Scripts/python.exe`) before system Python.
  Otherwise the spawned process gets `ModuleNotFoundError` because system Python lacks Flask.
- Electron's `app.isPackaged` is undefined outside Electron context — guard with
  `app && typeof app.isPackaged !== 'undefined'` when modules are also imported by Node directly.
- Use `windowsHide: true` in `child_process.spawn()` to prevent a console window flash on Windows.
- For graceful shutdown on Windows, use `taskkill /PID /T /F` instead of `SIGTERM` (not supported).
- Separate Chromium: Playwright needs its own Chromium (`playwright install chromium`).
  Electron's bundled Chromium cannot be reused because Playwright requires persistent browser
  contexts with a custom user data directory, which is incompatible with Electron's embedded binary.
  The original shared-Chromium strategy (ADR-006) was abandoned after discovering this limitation.

### 12.7 Production-Readiness Is Not a Phase
- Retrofitting i18n into 460+ hardcoded strings across 7 route files, 19 JS modules, and 1 HTML
  template cost an entire session. Had `t()` been used from the first endpoint, it would have been
  free — just a different function call for the same string.
- Same for accessibility: adding ARIA to 50+ elements, keyboard navigation to 5 components, and
  focus traps to 4 modals after the fact required re-reading every file. Building it in means
  writing `<button>` instead of `<span onclick>` — zero extra effort.
- SQLite WAL mode is a 2-line PRAGMA. Retry with backoff is a 30-line wrapper. Both should be
  in the first commit, not discovered after production issues.
- Security headers, auth middleware, rate limiting, and error handlers should be in `create_app()`
  from the very first endpoint. Adding them later means auditing every existing route.
- **Rule**: Section 8 checklist items are requirements for Phase 5-6 (Build), not Phase 12 (Security Audit).
  The Security Audit confirms they were done, not does them for the first time.

### 12.8 GitHub Issue Lifecycle
- Every TASK-NNN MUST have a corresponding GitHub issue. Create it at the START of the
  implementation (Phase 1, alongside project planning), not retroactively after delivery.
- Use `gh issue create --title "..." --label "..." --body "..."` to create issues via CLI.
- Update the issue with progress comments during long-running tasks if needed.
- Close the issue with `gh issue close N --comment "Completed in commit <hash>."` when pushed.
- If an existing open issue matches the task being implemented, use that issue instead of creating a duplicate.
- **Rule**: The Release Engineer checklist includes "GitHub Issue closed" — a task is NOT done until the issue is closed.

### 12.9 Branch-First Workflow
- Always create a new branch from `master` BEFORE writing any code. Never start work on `master`
  or on an existing branch belonging to a different task.
- Branch names MUST indicate the type of work: `feature/`, `fix/`, `refactor/`, `docs/`, `test/`, `chore/`.
  This makes it immediately clear from the branch name what kind of change to expect.
- Include the TASK-ID in feature branch names (e.g., `feature/task-030-smart-resume-reuse-m1`)
  so branches are traceable to their GitHub issue and planning artifacts.
- One branch = one PR = one logical change. Don't pile unrelated changes into one branch.
- After PR is merged, delete the remote branch to keep the repo clean.
