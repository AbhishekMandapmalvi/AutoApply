# Release Engineering Patterns

## CI/CD Pipeline Stages
```
Lint → Build → Unit Test → Integration Test → Security Scan → Package → Deploy Staging → Deploy Prod
```

## Semantic Versioning (semver)
```
MAJOR.MINOR.PATCH — e.g., 2.1.3
MAJOR: breaking changes (incompatible API)
MINOR: new features (backward compatible)
PATCH: bug fixes (backward compatible)
Pre-release: 2.1.3-beta.1
```

## Conventional Commits
```
feat(auth): add JWT refresh endpoint       → bumps MINOR
fix(cart): correct tax calculation          → bumps PATCH
feat(api)!: remove deprecated v1 endpoints → bumps MAJOR (! = breaking)
docs(readme): update quick start
chore(deps): bump lodash to 4.17.21
test(order): add edge case for empty cart
ci(pipeline): add security scan stage
perf(query): optimize user search index
```

## Deployment Strategies
| Strategy | Zero-Downtime | Rollback Speed | Risk | Complexity |
|----------|:---:|:---:|:---:|:---:|
| Big Bang | ❌ | Slow | High | Low |
| Rolling | ✅ | Medium | Medium | Medium |
| Blue/Green | ✅ | Fast (switch) | Low | Medium |
| Canary | ✅ | Fast (route) | Very Low | High |
| Feature Flags | ✅ | Instant (toggle) | Very Low | High |

## Dockerfile Best Practices
```dockerfile
# 1. Specific version (never :latest)
FROM node:20.11-alpine AS builder
# 2. Dependencies first (cache layer)
COPY package*.json ./
RUN npm ci --production
# 3. Source code (changes most)
COPY . .
RUN npm run build
# 4. Minimal runtime image
FROM node:20.11-alpine
RUN adduser -D appuser
USER appuser
COPY --from=builder /app/dist /app
HEALTHCHECK --interval=30s CMD wget -q --spider http://localhost:3000/health
ENTRYPOINT ["node", "/app/index.js"]
```

## GitHub Repository & PR Workflow

### Branch Strategy (Gitflow-lite)
```
master (release — protected, squash-merge only, enforce admins)
  └── develop (integration — protected, CI required)
        ├── feature/task-030-smart-resume-reuse-m1
        ├── fix/login-timeout
        ├── refactor/split-bot-loop
        ├── docs/update-api-reference
        ├── test/applier-edge-cases
        └── chore/upgrade-playwright
  ← release/vX.Y.Z (develop → master)
  ← hotfix/critical-fix (master → master, back-merge → develop)
```

### PR Lifecycle
```
1. Start from develop: git checkout develop && git pull origin develop
2. Create branch: git checkout -b type/short-description
3. Develop + test locally: ruff check . && python -m pytest tests/ -v
4. Push: git push -u origin type/short-description
5. Open PR targeting develop: gh pr create --base develop --title "..." --body "..."
6. CI runs: lint → test → security (all 3 must pass)
7. Review: address feedback with new commits (no force-push)
8. Merge to develop, delete remote branch
9. Release: develop → master via release/ branch PR (squash-merge)
```

### PR Template Sections
```markdown
## Summary         — What and why (1-3 sentences)
## Changes         — Bullet list of specific changes
## Test plan       — Checkboxes: tests pass, lint pass, no security issues
## Related issues  — Closes #N, Fixes #N
```

### GitHub Actions (AutoApply-specific)
```yaml
# CI (.github/workflows/ci.yml)
Triggers: push, pull_request
Jobs: lint (ruff), test (pytest), security (pip-audit)
Node.js 24 actions: checkout@v6, setup-python@v6

# Release (.github/workflows/release.yml)
Triggers: v* tag push
Jobs: 3 parallel OS builds (Windows/macOS/Linux)
Outputs: .exe, .dmg, .AppImage → GitHub Releases
```

### Branch Protection Rules

| Rule | `master` | `develop` |
|------|----------|-----------|
| PR required | Yes | Yes |
| CI checks (lint, test, security) | Yes (strict) | Yes (strict) |
| Enforce for admins | Yes | No |
| Squash-merge only (linear history) | Yes | No |
| Force-push blocked | Yes | Yes |
| Deletion blocked | Yes | Yes |
| Dismiss stale reviews | Yes | Yes |
| Conversation resolution required | Yes | Yes |
| GitHub Ruleset (zero bypass) | Yes | No |

CODEOWNERS: `@AbhishekMandapmalvi`

### gh CLI Quick Reference
```bash
# PRs
gh pr create --title "feat: ..." --body "..."
gh pr list
gh pr view 123
gh pr merge 123 --squash --delete-branch

# Issues
gh issue create --title "..." --body "..."
gh issue list --label bug
gh issue close 123

# Releases
gh release create v1.9.0 --generate-notes
gh release view v1.9.0
gh release upload v1.9.0 ./dist/*

# Actions
gh run list
gh run view 123456
gh run watch 123456
```

## Rollback Decision Matrix
| Signal | Auto-Rollback | Manual Decision |
|--------|:---:|:---:|
| Health check fails | ✅ | |
| Error rate > 5% | ✅ | |
| Error rate 1-5% | | ✅ |
| Latency > 2× baseline | | ✅ |
| Business metric drop | | ✅ |
| Single user report | | ✅ |
