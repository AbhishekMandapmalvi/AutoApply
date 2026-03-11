# Shared Workflows — Single Source of Truth

> Referenced by CLAUDE.md and all skill files. Update HERE, not in individual files.
> Last updated: 2026-03-11

---

## 1. Branch Lifecycle

### Branch Naming Convention
```
type/short-description
```

| Type | When | Example |
|------|------|---------|
| `feature/` | New functionality (include TASK-ID) | `feature/task-030-smart-resume-reuse-m1` |
| `fix/` | Bug fixes | `fix/mypy-type-error-experience-calc` |
| `refactor/` | Code restructuring, no behavior change | `refactor/extract-db-helpers` |
| `docs/` | Documentation only | `docs/update-readme-test-count` |
| `test/` | Test additions/fixes only | `test/add-kb-integration-tests` |
| `chore/` | Maintenance, deps, CI config | `chore/upgrade-playwright` |

### Mandatory Steps (every code change)
```bash
# 1. Start from clean master
git checkout master && git pull origin master

# 2. Create branch (BEFORE any code changes)
git checkout -b type/short-description

# 3. Do work, commit with conventional messages
git add <files>
git commit -m "type: short summary

Optional body — explain WHY, not WHAT.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"

# 4. Push
git push -u origin type/short-description

# 5. Open PR
gh pr create --title "type: short summary" --body "..."

# 6. CI must pass (lint, test, security) before merge

# 7. Squash-merge to master, delete remote branch
```

### Rules
- One branch per task. Never reuse branches across unrelated tasks.
- Never work directly on `master`. Never force-push to `master`.
- Feature branches MUST include TASK-ID for traceability.
- After merge, delete the remote branch to keep the repo clean.

---

## 2. GitHub Issue Lifecycle

### Create (Phase 0a — before any work)
```bash
gh issue create \
  --title "TASK-NNN: Short description" \
  --label "backend,smart-reuse" \
  --body "## Scope
- What this issue covers

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Files
- \`path/to/file.py\` — description"
```

### Update (during work, if long-running)
```bash
gh issue comment NNN --body "Progress: completed X, starting Y. No blockers."
```

### Close (Phase 14 — after merge)
```bash
gh issue close NNN --comment "Completed in commit $(git rev-parse --short HEAD). PR #NN merged."
```

### Rules
- Every TASK-NNN MUST have a GitHub issue. Create at Phase 0a, close at Phase 14.
- If an existing open issue matches the task, use it instead of creating a duplicate.
- A task is NOT done until the issue is closed.

---

## 3. PR Checklist

Before opening a PR, verify:

- [ ] Branch created from latest `master` using naming convention (§1)
- [ ] `ruff check .` passes (lint)
- [ ] `mypy app.py app_state.py run.py config/ core/ db/ bot/ routes/` passes (type check)
- [ ] `python -m pytest tests/ -v` passes (all tests)
- [ ] New code has unit tests (coverage target: >=90% line, >=85% branch)
- [ ] `CHANGELOG.md` updated under `[Unreleased]` if user-facing change
- [ ] GitHub issue referenced in commit body (`Closes #NNN`)

PR description MUST include:
```markdown
## Summary
<1-3 bullet points>

## Changes
<bullet list of specific changes>

## Test plan
- [ ] Tests pass locally
- [ ] Lint clean
- [ ] Coverage meets threshold

## Related issues
Closes #NNN
```

---

## 4. Scope Determination

Use this decision tree at Phase 1 (Project Planning) to classify task size:

```
Is the task a single-file bugfix or typo fix?
  YES → Small (< 50 LOC)
  NO ↓

Does the task touch ≤ 3 files with no new modules or DB changes?
  YES → Medium (50-300 LOC)
  NO ↓

Does the task require new modules, DB tables, API endpoints, or UI components?
  YES → Large (300+ LOC)
```

| Scope | Leadership | Design | Build | Test | Quality | Release |
|-------|-----------|--------|-------|------|---------|---------|
| Small | Inline PM | Inline SE | Full | Unit only | Quick scan | Inline |
| Medium | Full PM | Full SE | Full | Full | Full audit | Full |
| Large | Full PgM+PM | Full SE+AWS | Full | Full+Perf | Full report | Full pkg |

### Role Activation by Task Type

| Task Type | Roles (in order) |
|-----------|-----------------|
| Backend feature | PgM → PjM → PM → RA → SE → BE → UT → IT → SecE → Doc → RE |
| Frontend feature | PgM → PjM → PM → RA → SE → FE → UT → IT → SecE → Doc → RE |
| Full-stack feature | PgM → PjM → PM → RA → SE → BE+FE → UT → IT → SecE → Doc → RE |
| Bugfix (small) | PjM(inline) → BE or FE → UT → Doc(inline) → RE(inline) |
| Docs only | PjM(inline) → Doc → RE(inline) |
| Test only | PjM(inline) → UT or IT → RE(inline) |

---

## 5. Traceability Matrix Rules

| Rule | Enforcement |
|------|-------------|
| Every FR must map to ≥1 design component | System Engineer checks at Phase 4 gate |
| Every FR must have ≥1 unit test | Unit Tester checks at Phase 10 gate |
| Every NFR must have a validation method | Requirements Analyst checks at Phase 3 gate |
| Every row must have all columns filled | Release Engineer checks at Phase 14 gate |
| Zero gaps allowed for release | PR blocked until all rows are ✅ |

Complete the matrix at Phase 14 using this template:
```
| Req ID | Title | Design Ref | Source Files | Unit Tests | Integ Tests | Docs | Security | Status |
```
