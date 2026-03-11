# Contributing to AutoApply

Thank you for your interest in contributing! This guide covers the workflow, conventions, and quality bar for all contributions.

---

## Getting Started

```bash
git clone https://github.com/AbhishekMandapmalvi/AutoApply.git
cd AutoApply
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS/Linux
pip install -e ".[dev]"
playwright install chromium
cd electron && npm install && cd ..
```

---

## Branch Naming

Use the format `type/short-description`:

| Type | When | Example |
|------|------|---------|
| `feature/` | New functionality | `feature/locale-switcher` |
| `fix/` | Bug fix | `fix/login-timeout` |
| `refactor/` | Code restructuring (no behavior change) | `refactor/split-bot-loop` |
| `docs/` | Documentation only | `docs/update-api-reference` |
| `test/` | Test additions or fixes | `test/applier-edge-cases` |
| `chore/` | CI, deps, tooling | `chore/upgrade-playwright` |

---

## Commit Messages

Follow this format:

```
<type>: <short summary in imperative mood>

<optional body — explain WHY, not WHAT>

Co-Authored-By: Name <email>   (if applicable)
```

**Types**: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `perf`, `security`

**Examples**:
```
feat: add Spanish locale translation
fix: prevent duplicate bot thread on rapid start clicks
refactor: extract scoring logic from filter.py
test: add boundary tests for salary scoring
docs: document screening answers configuration
chore: pin playwright to 1.58.0
```

**Rules**:
- Keep the summary under 72 characters
- Use imperative mood ("add", not "added" or "adds")
- Reference issue numbers in the body when applicable (`Closes #42`)

---

## Pull Request Process

### Before opening a PR

1. **Create a branch** from `master` using the naming convention above
2. **Make focused changes** — one feature or fix per PR
3. **Run the full check suite locally**:
   ```bash
   ruff check .                    # Lint
   python -m pytest tests/ -v      # Tests (738+ must pass)
   ```
4. **Update documentation** if your change affects user-facing behavior:
   - `CHANGELOG.md` — add entry under `[Unreleased]`
   - `docs/` guides — update any affected guides
   - `README.md` — update if features/test count changed

### PR requirements

| Requirement | Details |
|-------------|---------|
| **Title** | Under 72 characters, describes the change |
| **Description** | Fill out the PR template (summary, changes, test plan) |
| **CI passes** | All 3 checks must be green: `lint`, `test`, `security` |
| **Up-to-date** | Branch must be current with `master` |
| **Conversations resolved** | All review comments must be addressed |
| **Tests included** | New code must have corresponding tests |
| **No secrets** | Never commit API keys, tokens, or credentials |

### PR size guidelines

| Size | LOC changed | Expectation |
|------|-------------|-------------|
| Small | < 50 | Quick review, can merge same day |
| Medium | 50–300 | Detailed review, may need revisions |
| Large | 300+ | Should be broken into smaller PRs when possible |

### Review process

1. Open a PR against `master`
2. CI runs automatically (lint, test, security)
3. Codeowner (`@AbhishekMandapmalvi`) is auto-assigned for review
4. Address any review feedback with new commits (don't force-push during review)
5. Once approved and CI is green, squash-merge

---

## Code Standards

### Python

- **Style**: PEP 8 enforced by `ruff` (line length 100)
- **Types**: Type hints encouraged; `mypy` runs in CI
- **Imports**: sorted by `ruff` (isort rules)
- **Strings**: User-facing strings must use `t()` for i18n
- **Logging**: Use `logging.getLogger(__name__)`, never `print()`
- **Security**: Validate inputs at boundaries, no `shell=True`, parameterized SQL

### JavaScript

- **Style**: Vanilla JS, ES modules (no build step)
- **Accessibility**: Semantic HTML, ARIA attributes, keyboard navigation
- **i18n**: Use `data-i18n` attributes or `t()` from `static/js/i18n.js`

### Tests

- **Framework**: pytest
- **Coverage target**: 80%+ line coverage on new code
- **Fixtures**: Use `tmp_path` for filesystem tests
- **Auth**: Tests use `AUTOAPPLY_DEV=1` to bypass auth (via conftest.py autouse fixture)
- **Error paths**: Test both happy paths and error cases

---

## What NOT to do

- Don't push directly to `master` (use PRs)
- Don't force-push to `master` (branch protection blocks this)
- Don't merge with failing CI checks
- Don't commit `.env`, API keys, or `config.json` with real data
- Don't add dependencies without pinning exact versions in `pyproject.toml`
- Don't skip tests with `@pytest.mark.skip` without an explanation

---

## Issue Guidelines

- **Bugs**: Use the bug report template. Include OS, Python version, and logs.
- **Features**: Use the feature request template. Describe the problem first.
- **Questions**: Open a discussion or issue tagged `question`.

---

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
