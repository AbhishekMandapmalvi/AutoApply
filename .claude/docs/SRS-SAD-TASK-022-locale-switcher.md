# SRS + SAD: Locale Switcher UI (TASK-022)

**Document ID**: SRS-SAD-TASK-022
**Date**: 2026-03-11
**Status**: approved
**GitHub Issue**: #8

---

## 1. Summary

Add a language dropdown to the Settings screen that lets users switch the UI locale.
Persist the choice in `localStorage` so it survives page reloads. Backend locale is
set via a new `PUT /api/locale` endpoint that updates the backend `set_locale()`.

---

## 2. Functional Requirements

### FR-131: Locale Dropdown in Settings

**Description**: A `<select>` dropdown in the Settings screen SHALL list all available
locales and allow the user to switch language.

**Priority**: P0 | **Source**: US (QOL-3, issue #8)

**Acceptance Criteria**:
- **AC-131-1**: Given the Settings screen, When the user opens it, Then a language dropdown
  is visible with all available locales from `GET /api/locales`.
- **AC-131-2**: Given the dropdown, When the user selects a locale, Then the frontend
  calls `setLocale(code)` and all UI text updates immediately without page reload.

### FR-132: Locale Persistence

**Description**: The selected locale SHALL be persisted in `localStorage` and restored
on next page load.

**Priority**: P0

**Acceptance Criteria**:
- **AC-132-1**: Given the user selects "es", When the page is reloaded, Then the locale
  is "es" (read from `localStorage`).
- **AC-132-2**: Given `localStorage` has no locale, When the page loads, Then default "en" is used.

### FR-133: Backend Locale Sync

**Description**: When the user switches locale, the backend's active locale SHALL be
updated so that backend error messages use the correct language.

**Priority**: P1

**Acceptance Criteria**:
- **AC-133-1**: Given the user selects "es", When `PUT /api/locale` is called with
  `{"locale": "es"}`, Then the backend `set_locale("es")` is called and returns 200.
- **AC-133-2**: Given an invalid locale code, When `PUT /api/locale` is called, Then
  the backend returns 400.

### FR-134: Locale Display Names

**Description**: The dropdown SHALL show human-readable language names, not just codes.

**Priority**: P1

**Acceptance Criteria**:
- **AC-134-1**: Given locale "en", Then the dropdown shows "English".
- **AC-134-2**: Given locale "es", Then the dropdown shows "Español".

---

## 3. Non-Functional Requirements

### NFR-022-01: i18n — All new strings use `t()` / `data-i18n`
### NFR-022-02: Accessibility — Dropdown has proper label and ARIA
### NFR-022-03: No Breaking Changes — Default behavior unchanged when only en.json exists

---

## 4. Design

### 4.1 Backend: `PUT /api/locale`

Add to `routes/lifecycle.py`:

```python
@lifecycle_bp.route("/api/locale", methods=["PUT"])
def set_locale_endpoint():
    data = request.get_json(silent=True) or {}
    locale = data.get("locale", "")
    available = get_available_locales()
    if locale not in available:
        abort(400, description=t("errors.bad_request"))
    set_locale(locale)
    return jsonify({"locale": locale})
```

### 4.2 Frontend: i18n.js changes

- `detectLocale()`: Check `localStorage.getItem('autoapply_locale')` first
- `setLocale()`: After loading, save to `localStorage.setItem('autoapply_locale', locale)`
- `setLocale()`: Call `PUT /api/locale` to sync backend

### 4.3 Frontend: settings.js changes

- `loadSettings()`: Fetch `GET /api/locales`, populate dropdown, set current value
- Add `onLocaleChange()`: Read dropdown value, call `setLocale()` from i18n.js

### 4.4 HTML: Add dropdown to Settings

Add a "Language" section before "Profile" in the settings card:

```html
<h3 data-i18n="settings.section_language">Language</h3>
<div class="form-group">
  <label data-i18n="settings.label_language">Language</label>
  <select class="form-control" id="set-locale" onchange="onLocaleChange()"
          aria-label="Select language"></select>
</div>
```

### 4.5 Locale display name map

```javascript
const LOCALE_NAMES = {
  en: 'English',
  es: 'Español',
  fr: 'Français',
  de: 'Deutsch',
  pt: 'Português',
  ja: '日本語',
  zh: '中文',
  ko: '한국어',
};
```

Fallback: show the code itself if not in map.

---

## 5. Implementation Plan

| Order | Task | Files |
|-------|------|-------|
| 1 | Add `PUT /api/locale` endpoint | `routes/lifecycle.py` |
| 2 | Update `i18n.js`: localStorage persist + backend sync | `static/js/i18n.js` |
| 3 | Add locale dropdown to settings HTML | `templates/index.html` |
| 4 | Add `onLocaleChange()` + populate dropdown in settings.js | `static/js/settings.js` |
| 5 | Add i18n keys | `static/locales/en.json` |
| 6 | Export `onLocaleChange` in app.js | `static/js/app.js` |
| 7 | Write tests | `tests/test_locale_switcher.py` |

---

## 6. Traceability

| Requirement | Source Files | Tests |
|-------------|-------------|-------|
| FR-131 | `templates/index.html`, `static/js/settings.js` | manual + test |
| FR-132 | `static/js/i18n.js` | test |
| FR-133 | `routes/lifecycle.py` | test |
| FR-134 | `static/js/settings.js` | test |
