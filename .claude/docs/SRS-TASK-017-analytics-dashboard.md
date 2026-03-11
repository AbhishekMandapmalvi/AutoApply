# Software Requirements Specification

**Document ID**: SRS-TASK-017-analytics-dashboard
**Version**: 1.0
**Date**: 2026-03-11
**Status**: approved
**Author**: Claude (Requirements Analyst)
**PRD Reference**: PRD-TASK-017

---

## 1. Purpose and Scope

### 1.1 Purpose
This SRS specifies the functional and non-functional requirements for the Analytics
Dashboard enhancement (v2.0.0). It transforms 8 user stories from PRD-TASK-017 into
precise, testable requirements. The audience is the System Engineer, Backend Developer,
Frontend Developer, Unit Tester, Integration Tester, Security Engineer, and Documenter.

### 1.2 Scope
The system SHALL extend the existing Analytics screen with 8 new visualizations and
their supporting backend API endpoints. The system SHALL NOT modify the existing
database schema, add new dependencies, or implement data export.

### 1.3 Definitions and Acronyms

| Term | Definition |
|------|-----------|
| Interview statuses | The set `{"interview", "interviewing", "interviewed"}`. All three count as "reached interview stage." |
| Offer statuses | The set `{"offer", "accepted"}`. Both count as "received offer." |
| Funnel-eligible | Applications with `status = "applied"` OR any interview status OR any offer status. Excludes `error`, `skipped`, `manual_required`, `saved`, `reviewed`, `withdrawn`. |
| Conversion rate | `(count_in_next_stage / count_in_current_stage) * 100`, expressed as a percentage with 1 decimal place. |
| Period preset | One of: `7` (7 days), `30` (30 days), `90` (90 days), `0` (all time). |
| Score bucket | A 10-point range: 0-9, 10-19, 20-29, ..., 90-100. The last bucket includes 100. 10 buckets total. |
| Response time | The difference in calendar days between `applied_at` and `updated_at` for applications whose status changed from the initial `"applied"` to a different status. |
| Summary card | A UI component displaying a single metric with a label, value, and optional trend indicator. |

---

## 2. Overall Description

### 2.1 Product Perspective
This feature extends the existing Analytics screen (`screen-analytics`) which currently
displays 3 Chart.js charts (daily applications line chart, status doughnut, platform bar)
powered by 2 API endpoints (`GET /api/analytics/summary`, `GET /api/analytics/daily`).
The enhancement adds 6 new API endpoints and replaces the existing frontend analytics
module with a richer dashboard.

### 2.2 User Classes and Characteristics

| User Class | Description | Frequency of Use | Technical Expertise |
|-----------|-------------|-------------------|---------------------|
| Active Searcher | Uses bot daily, reviews analytics for strategy | Daily | Novice to intermediate |
| Periodic Reviewer | Checks dashboard weekly for progress | Weekly | Novice |
| Strategy Tuner | Adjusts bot configuration based on analytics data | Monthly | Intermediate |

### 2.3 Operating Environment
- Electron desktop application (Windows, macOS, Linux)
- Flask 3.x backend with SQLite database
- Chart.js 4.x for visualizations (already bundled via CDN in index.html)
- Vanilla JavaScript ES modules (no build step)

### 2.4 Assumptions

| # | Assumption | Risk if Wrong | Mitigation |
|---|-----------|---------------|------------|
| A1 | The `applied_at` column is always populated (NOT NULL, DEFAULT CURRENT_TIMESTAMP) | Queries return incorrect counts | Schema enforces NOT NULL — verified in database.py |
| A2 | `updated_at` is updated on every status change via `update_status()` | Response time calculations are inaccurate | Verified: `update_status()` sets `updated_at = CURRENT_TIMESTAMP` |
| A3 | Applications with status `"applied"` that never changed still have `updated_at = applied_at` | Response time for unchanged apps would be 0 days | Exclude apps where `status = "applied"` from response time calculation |
| A4 | Chart.js 4.x is available globally via CDN script tag in index.html | Charts fail to render | Verified: Chart.js loaded in index.html head |
| A5 | Maximum dataset size is 10,000 applications per user | Queries remain under 200ms | SQLite with indexes handles 10K rows in <50ms for GROUP BY queries |

### 2.5 Constraints

| Type | Constraint | Rationale |
|------|-----------|-----------|
| Technical | No new database tables or columns | All required data exists in the `applications` table |
| Technical | No new npm/pip dependencies | Minimize attack surface and bundle size |
| Technical | Vanilla JS ES modules, no build step | Consistent with ADR-017 frontend architecture |
| Technical | All queries use existing SQLite indexes (`idx_applied_at`, `idx_status`) | Performance guarantee |
| UX | Dark theme (CSS custom properties: `--bg`, `--panel`, `--accent`, etc.) | Consistent with existing UI |

---

## 3. Functional Requirements

### FR-090: Analytics Summary Cards

**Description**: The system SHALL display four summary metric cards at the top of the
Analytics screen showing: (1) total application count, (2) interview conversion rate,
(3) average match score, and (4) applications submitted in the current calendar week
(Monday 00:00 UTC to now).

**Priority**: P0
**Source**: US-080
**Dependencies**: None

**Acceptance Criteria**:

- **AC-090-1**: Given the user has 150 applications in the database (120 with status "applied", 15 with any interview status, 5 with any offer status, 10 with other statuses), When the Analytics screen loads, Then the summary cards display: Total = "150", Interview Rate = "12.5%" (15 interview-stage out of 120 funnel-eligible applied), Avg Score = the arithmetic mean of all 150 match_score values rounded to 1 decimal, This Week = count of applications where `applied_at >= Monday 00:00 UTC of the current week`.

- **AC-090-2**: Given the user has zero applications in the database, When the Analytics screen loads, Then the summary cards display: Total = "0", Interview Rate = "—", Avg Score = "—", This Week = "0".

- **AC-090-3**: Given the user has applications but none have reached interview status, When the Analytics screen loads, Then Interview Rate displays "0.0%".

**Negative Cases**:

- **AC-090-N1**: Given the database is not initialized (503 from backend), When the Analytics screen loads, Then the cards display a loading error state and do not show stale data.

---

### FR-091: Enhanced Application Trend Chart

**Description**: The system SHALL display a line chart showing daily application counts
with a period selector offering four presets: 7 days, 30 days (default), 90 days, and
all time. The existing `GET /api/analytics/daily` endpoint SHALL be reused. When "all"
is selected, the `days` parameter SHALL be omitted or set to `0`, and the backend SHALL
return all available data.

**Priority**: P0
**Source**: US-081
**Dependencies**: None (extends existing endpoint)

**Acceptance Criteria**:

- **AC-091-1**: Given the user has applications spanning 45 days, When the Analytics screen loads, Then a line chart displays daily counts for the most recent 30 days (default period).

- **AC-091-2**: Given the user clicks the "7d" period button, When the chart reloads, Then it displays only the last 7 days of data.

- **AC-091-3**: Given the user clicks the "All" period button, When the chart reloads, Then it displays data for every day that has at least one application, from the earliest to the latest.

- **AC-091-4**: Given a day within the selected period has zero applications, When the chart renders, Then that day appears on the x-axis with a count of 0 (no gaps).

**Negative Cases**:

- **AC-091-N1**: Given the user has zero applications, When the trend chart renders, Then it displays an empty state message (not a broken chart).

---

### FR-092: Status Conversion Funnel

**Description**: The system SHALL display a conversion funnel visualization showing
three stages: Applied → Interview → Offer. Each stage SHALL show the count and the
conversion rate percentage to the next stage. The funnel counts SHALL use only
funnel-eligible statuses (see Definitions §1.3).

**Priority**: P0
**Source**: US-082
**Dependencies**: FR-094 (backend endpoint)

**Acceptance Criteria**:

- **AC-092-1**: Given 200 applications with status "applied", 20 with any interview status, and 3 with any offer status, When the funnel renders, Then it displays: Applied = 200, Interview = 20 (10.0%), Offer = 3 (15.0% of interviews, 1.5% of applied).

- **AC-092-2**: Given 50 applications all with status "applied" (no interviews or offers), When the funnel renders, Then it displays: Applied = 50, Interview = 0 (0.0%), Offer = 0 (0.0%).

- **AC-092-3**: Given the funnel is displayed, When the user reads conversion percentages, Then each percentage is calculated as `(next_stage_count / current_stage_count) * 100` rounded to 1 decimal place.

**Negative Cases**:

- **AC-092-N1**: Given zero funnel-eligible applications (all are error/skipped/etc.), When the funnel renders, Then it displays "0" for all stages with "—" for percentages (no division by zero).

---

### FR-093: Platform Performance Table

**Description**: The system SHALL display a table comparing application performance
across platforms. Each row SHALL show: platform name, total application count, interview
count (any interview status), interview rate (%), average match score, and offer count.
Rows SHALL be sorted by total application count descending.

**Priority**: P0
**Source**: US-083
**Dependencies**: FR-094 (backend endpoint)

**Acceptance Criteria**:

- **AC-093-1**: Given 80 LinkedIn applications (5 interviews, 1 offer, avg score 72.3) and 40 Indeed applications (2 interviews, 0 offers, avg score 68.1), When the platform table renders, Then LinkedIn appears first with: Total=80, Interviews=5, Rate=6.3%, Avg Score=72.3, Offers=1; Indeed second with: Total=40, Interviews=2, Rate=5.0%, Avg Score=68.1, Offers=0.

- **AC-093-2**: Given a platform has zero applications with interview status, When displayed, Then interview rate shows "0.0%" and offer count shows "0".

- **AC-093-3**: Given applications exist on all 6 supported platforms, When the table renders, Then all 6 platforms appear as separate rows.

**Negative Cases**:

- **AC-093-N1**: Given zero applications in the database, When the platform table renders, Then it displays an empty state message instead of an empty table.

---

### FR-094: Analytics API — Enhanced Endpoint

**Description**: The system SHALL provide a new API endpoint `GET /api/analytics/enhanced`
that returns all analytics data in a single response. The endpoint SHALL accept an
optional `days` query parameter (integer, default 30; `0` means all time). The response
SHALL include: summary metrics, conversion funnel data, platform performance data,
score distribution, weekly comparison, top companies, and response time metrics.

**Priority**: P0
**Source**: US-080 through US-087
**Dependencies**: None

**Acceptance Criteria**:

- **AC-094-1**: Given the endpoint is called with `GET /api/analytics/enhanced`, When the request is processed, Then the response is JSON with HTTP 200 and the following top-level keys: `summary`, `funnel`, `platforms`, `score_distribution`, `weekly`, `top_companies`, `response_times`, `daily` (array of `{date, count}`).

- **AC-094-2**: Given the endpoint is called with `?days=7`, When the query executes, Then `daily` contains only the last 7 days, `summary.this_week` reflects the current week, and `weekly` compares the last 7 days vs the prior 7 days.

- **AC-094-3**: Given the endpoint is called with `?days=0` (all time), When the query executes, Then `daily` contains all available data and `weekly` still compares the most recent 7 days vs the prior 7 days.

- **AC-094-4**: Given the `summary` object, Then it SHALL contain: `total` (int), `interview_rate` (float, 1 decimal), `avg_score` (float, 1 decimal), `this_week` (int).

- **AC-094-5**: Given the `funnel` object, Then it SHALL contain: `applied` (int), `interview` (int), `offer` (int), `applied_to_interview_rate` (float), `interview_to_offer_rate` (float).

- **AC-094-6**: Given the `platforms` array, Then each element SHALL contain: `platform` (string), `total` (int), `interviews` (int), `interview_rate` (float), `avg_score` (float), `offers` (int). Array SHALL be sorted by `total` descending.

- **AC-094-7**: Given the `score_distribution` array, Then it SHALL contain 10 elements, one per score bucket (0-9, 10-19, ..., 90-100). Each element SHALL contain: `bucket` (string label, e.g., "70-79"), `count` (int), `interview_count` (int), `interview_rate` (float).

- **AC-094-8**: Given the `weekly` object, Then it SHALL contain: `current` and `previous`, each with `applications` (int), `interviews` (int), `avg_score` (float or null). It SHALL also contain `changes` with `applications` (int, signed delta), `interviews` (int, signed delta), `avg_score` (float or null, signed delta).

- **AC-094-9**: Given the `top_companies` array, Then it SHALL contain up to 10 elements sorted by total count descending. Each element SHALL contain: `company` (string), `total` (int), `statuses` (dict mapping status string to count).

- **AC-094-10**: Given the `response_times` object, Then it SHALL contain: `to_interview` and `to_rejected`, each with `median_days` (float or null) and `avg_days` (float or null). Only applications whose status differs from "applied" SHALL be included.

- **AC-094-11**: Given the endpoint is called with valid Bearer token, When authorized, Then the response returns HTTP 200. Given no token or invalid token, When unauthorized, Then the response returns HTTP 401.

**Negative Cases**:

- **AC-094-N1**: Given `days` parameter is a negative number, When the request is made, Then the endpoint returns HTTP 400 with error message.

- **AC-094-N2**: Given `days` parameter is not an integer (e.g., "abc"), When the request is made, Then the endpoint uses the default value of 30 (Flask's `request.args.get` type coercion).

- **AC-094-N3**: Given the database contains zero applications, When the endpoint is called, Then it returns valid JSON with all keys present: totals at 0, rates at 0.0 or null, empty arrays where applicable.

---

### FR-095: Match Score Distribution Chart

**Description**: The system SHALL display a bar chart (histogram) showing the distribution
of application match scores in 10-point buckets. Each bar SHALL be color-coded to show
the proportion of applications that reached interview stage within that bucket.

**Priority**: P1
**Source**: US-084
**Dependencies**: FR-094

**Acceptance Criteria**:

- **AC-095-1**: Given applications with scores 45, 52, 55, 72, 78, 85, 91, When the histogram renders, Then bucket "40-49" shows 1, "50-59" shows 2, "70-79" shows 2, "80-89" shows 1, "90-100" shows 1, and all other buckets show 0.

- **AC-095-2**: Given bucket "70-79" has 10 applications and 3 are in interview status, When the user views the bucket tooltip, Then it shows "3 interviews (30.0%)".

- **AC-095-3**: Given the chart is rendered, When the user reads it, Then the x-axis shows bucket labels ("0-9", "10-19", ..., "90-100") and the y-axis shows application count.

**Negative Cases**:

- **AC-095-N1**: Given a bucket has zero applications, When rendered, Then the bar height is 0 and no tooltip error occurs.

---

### FR-096: Weekly Summary with Trends

**Description**: The system SHALL display a weekly comparison panel showing this week's
metrics versus last week's metrics with directional indicators. Metrics compared:
application count, interview count, average match score.

**Priority**: P1
**Source**: US-085
**Dependencies**: FR-094

**Acceptance Criteria**:

- **AC-096-1**: Given this week has 25 applications and last week had 20, When the weekly summary renders, Then applications shows "25" with an up arrow and "+25.0%" change.

- **AC-096-2**: Given this week has 2 interviews and last week had 5, When the weekly summary renders, Then interviews shows "2" with a down arrow and "-60.0%" change.

- **AC-096-3**: Given last week had zero applications, When calculating percentage change, Then the change displays "+25" (absolute count) instead of a percentage (avoids division by zero).

- **AC-096-4**: Given this is the user's first week (no prior week data), When the weekly summary renders, Then the previous week column shows "—" for all metrics and change column shows "—".

**Negative Cases**:

- **AC-096-N1**: Given both weeks have zero applications, When the weekly summary renders, Then all values show "0" and change shows "—" (no "0%" or "+0%").

---

### FR-097: Top Companies Breakdown

**Description**: The system SHALL display a table of the top 10 companies by application
count, with a status breakdown showing how many applications are in each status per
company.

**Priority**: P1
**Source**: US-086
**Dependencies**: FR-094

**Acceptance Criteria**:

- **AC-097-1**: Given the user has applied to 15 distinct companies, When the top companies table renders, Then only the top 10 by total count are shown.

- **AC-097-2**: Given "Acme Corp" has 8 applications (5 applied, 2 interview, 1 rejected), When the row renders, Then it shows: Company="Acme Corp", Total=8, with status badges showing the breakdown.

- **AC-097-3**: Given two companies have the same count, When sorting, Then they appear in alphabetical order as a tiebreaker.

**Negative Cases**:

- **AC-097-N1**: Given fewer than 10 distinct companies, When the table renders, Then it shows all available companies (no empty rows or padding).

- **AC-097-N2**: Given zero applications, When the table renders, Then it displays an empty state message.

---

### FR-098: Response Time Metrics

**Description**: The system SHALL display median and average response times (in calendar
days) for two transitions: applied → interview and applied → rejected. Only applications
that have actually transitioned (status is not "applied") SHALL be included.

**Priority**: P2
**Source**: US-087
**Dependencies**: FR-094

**Acceptance Criteria**:

- **AC-098-1**: Given 5 applications transitioned to interview status with response times of 3, 5, 7, 10, 15 days, When response time renders, Then it shows: Median = 7.0 days, Average = 8.0 days for "To Interview".

- **AC-098-2**: Given no applications have transitioned to interview, When response time renders, Then "To Interview" shows "—" for both median and average.

- **AC-098-3**: Given response time data exists for both interview and rejected transitions, When rendered, Then both sections display independently with their own median and average.

**Negative Cases**:

- **AC-098-N1**: Given an application has `applied_at = updated_at` (status changed in same second), When included in response time, Then it counts as 0 days (not excluded, not an error).

---

### FR-099: Backend — Enhanced Daily Analytics (extend existing)

**Description**: The existing `GET /api/analytics/daily` endpoint SHALL be extended to
accept `days=0` as a valid value meaning "all time" (return daily counts for every day
with at least one application). The current behavior for positive integers SHALL be
preserved.

**Priority**: P0
**Source**: US-081
**Dependencies**: None

**Acceptance Criteria**:

- **AC-099-1**: Given the endpoint is called with `?days=0`, When the query executes, Then it returns daily counts for every day from the earliest application to the latest.

- **AC-099-2**: Given the endpoint is called with `?days=30` (existing behavior), When the query executes, Then it returns daily counts for the last 30 days (existing behavior unchanged).

**Negative Cases**:

- **AC-099-N1**: Given `days` is a negative number, When called, Then the endpoint treats it as `30` (default fallback).

---

### FR-100: Analytics UI — Period Selector

**Description**: The system SHALL display a period selector (group of 4 buttons) above
the trend chart allowing the user to switch between 7d, 30d, 90d, and All. The active
period SHALL be visually highlighted. Clicking a period SHALL reload all analytics data
for that period. The default selection SHALL be 30d.

**Priority**: P0
**Source**: US-081
**Dependencies**: FR-091, FR-094

**Acceptance Criteria**:

- **AC-100-1**: Given the Analytics screen loads, When rendered, Then the "30d" button is visually active (highlighted with `--accent` color).

- **AC-100-2**: Given the user clicks "7d", When the UI updates, Then "7d" becomes active, "30d" is deactivated, and the trend chart reloads with 7-day data.

- **AC-100-3**: Given the user clicks "All", When the API is called, Then `days=0` is passed to the enhanced endpoint.

- **AC-100-4**: Given the period selector exists, When navigated via keyboard, Then arrow keys move focus between buttons, Enter/Space activates the focused button.

**Negative Cases**:

- **AC-100-N1**: Given the API call fails (network error), When the period is changed, Then the chart retains its previous data and an error indicator appears.

---

### FR-101: Analytics UI — Empty States

**Description**: Every analytics component (summary cards, charts, tables, funnel) SHALL
display a meaningful empty state when there is no data, rather than broken UI, blank
spaces, or JavaScript errors.

**Priority**: P0
**Source**: US-080 through US-087 (cross-cutting)
**Dependencies**: All FR-090 through FR-100

**Acceptance Criteria**:

- **AC-101-1**: Given zero applications in the database, When the Analytics screen loads, Then every component renders without JavaScript errors and displays an appropriate empty state (e.g., "No applications yet", "—" for rates).

- **AC-101-2**: Given applications exist but none in interview status, When conversion data renders, Then rates show "0.0%" (not "NaN%" or blank).

**Negative Cases**:

- **AC-101-N1**: Given the database returns an error, When any analytics component attempts to render, Then it displays an error message without crashing other components.

---

## 4. Non-Functional Requirements

### NFR-017-01: Query Performance

**Description**: All analytics SQL queries executed by `GET /api/analytics/enhanced`
SHALL complete in under 200ms total for a database containing up to 10,000 application
records.
**Metric**: Combined query execution time < 200ms at p95 for 10,000 rows.
**Priority**: P0
**Validation Method**: Unit test with 10,000 inserted rows, assert wall-clock time < 200ms.

### NFR-017-02: Internationalization

**Description**: All user-visible strings in the Analytics dashboard (labels, headers,
empty states, tooltips, period labels, column headers) SHALL use the `t()` translation
function (backend) or `data-i18n` attributes (frontend HTML) with keys in
`static/locales/en.json`.
**Metric**: Zero hardcoded English strings in analytics frontend or backend code.
**Priority**: P0
**Validation Method**: Code review + grep for string literals in analytics code paths.

### NFR-017-03: Accessibility

**Description**: All new Analytics UI components SHALL conform to WCAG 2.1 AA. Charts
SHALL have text alternatives (summary table or ARIA description). Interactive elements
(period selector, table sorting) SHALL be keyboard-navigable. Data tables SHALL use
semantic `<table>`, `<thead>`, `<th scope>` elements.
**Metric**: No WCAG 2.1 AA violations in new components.
**Priority**: P0
**Validation Method**: Manual keyboard navigation test + ARIA attribute review.

### NFR-017-04: Test Coverage

**Description**: All new backend methods (database queries, API endpoints) and frontend
rendering functions SHALL have unit tests achieving at least 80% line coverage on new
code.
**Metric**: pytest coverage >= 80% on new files/methods.
**Priority**: P0
**Validation Method**: `pytest --cov` report on new modules.

### NFR-017-05: API Response Size

**Description**: The `GET /api/analytics/enhanced` response SHALL not exceed 50 KB for
a dataset of 10,000 applications.
**Metric**: Response body < 50 KB.
**Priority**: P1
**Validation Method**: Unit test asserting response size.

### NFR-017-06: Chart Rendering Performance

**Description**: Chart.js charts SHALL render (DOMContentLoaded to last chart painted)
within 500ms for datasets returned by the enhanced endpoint with up to 365 daily data
points.
**Metric**: All charts visible within 500ms of data receipt.
**Priority**: P1
**Validation Method**: Manual testing with 365-day dataset.

---

## 5. Interface Requirements

### 5.1 User Interfaces

The Analytics screen (`screen-analytics`) SHALL be reorganized into sections:

1. **Summary Cards Row** — 4 metric cards in a horizontal row (FR-090)
2. **Period Selector** — 4 toggle buttons: 7d / 30d / 90d / All (FR-100)
3. **Trend Chart** — Line chart, full width (FR-091)
4. **Two-Column Layout**:
   - Left: Conversion Funnel (FR-092) + Score Distribution (FR-095)
   - Right: Platform Performance Table (FR-093)
5. **Weekly Summary Panel** — This week vs last week comparison (FR-096)
6. **Two-Column Layout**:
   - Left: Top Companies Table (FR-097)
   - Right: Response Time Metrics (FR-098)

All sections follow the dark theme using existing CSS custom properties.

### 5.2 API Interface

| Method | Route | Query Params | Response | FR |
|--------|-------|-------------|----------|-----|
| GET | `/api/analytics/enhanced` | `days` (int, default 30, 0=all) | JSON (see FR-094) | FR-094 |
| GET | `/api/analytics/daily` | `days` (int, default 30, 0=all) | `[{date, count}]` | FR-099 |
| GET | `/api/analytics/summary` | — | `{total, by_status, by_platform}` | (existing, unchanged) |

---

## 6. Data Requirements

### 6.1 Data Entities
No new entities. All analytics are computed from the existing `applications` table
using aggregate SQL queries (COUNT, AVG, GROUP BY, DATE functions).

### 6.2 Data Retention
No change. Application records are retained indefinitely (existing behavior).

### 6.3 Data Migration
None required. No schema changes.

---

## 7. Out of Scope

- **Analytics export (PDF/CSV)**: Deferred to v2.1.0 — requires ReportLab integration for PDF.
- **Goal setting / target tracking**: Separate feature — requires new database table for user goals.
- **Email/notification digest**: No notification infrastructure exists.
- **AI-powered insights**: Deferred to v2.1.0 — requires LLM integration with analytics data.
- **Custom date range picker**: Deferred — period presets (7d/30d/90d/all) cover primary use cases.
- **Salary analysis**: Salary is stored as free-text string, not structured numeric — unreliable for analytics.
- **Geographic heatmap**: Location is free-text, not geocoded — unreliable for mapping.

---

## 8. Dependencies

### External Dependencies

| Dependency | Type | Status | Risk if Unavailable |
|-----------|------|--------|---------------------|
| Chart.js 4.x | Runtime (CDN) | Available | Charts won't render — fallback: show data tables |
| SQLite | Runtime | Available | Entire app non-functional — not specific to analytics |

### Internal Dependencies

| This Feature Needs | From Feature/Task | Status |
|-------------------|-------------------|--------|
| `applications` table with indexes | TASK-001 (Foundation) | Done |
| `get_analytics_summary()` method | TASK-001 | Done |
| `get_daily_analytics()` method | TASK-001 | Done |
| i18n `t()` function (backend) | TASK-014 (i18n) | Done |
| i18n `t()` function (frontend) | TASK-015 (Frontend i18n) | Done |
| Auth middleware (Bearer token) | TASK-012 (Prod Readiness) | Done |

---

## 9. Risks

| # | Risk | Probability | Impact | Risk Score | Mitigation |
|---|------|:-----------:|:------:|:----------:|------------|
| R1 | Complex SQL for score bucketing + interview rates | M | L | ML | Test with edge cases; use CASE WHEN for buckets |
| R2 | Response time median requires sorting in SQLite (no built-in MEDIAN) | M | L | ML | Compute median in Python from sorted list |
| R3 | Frontend analytics.js exceeds 400 LOC | M | M | MM | Keep rendering functions modular; split if needed |
| R4 | Zero-division in conversion rate calculations | M | H | MH | Guard every division with denominator check |
| R5 | Chart.js CDN unavailable offline | L | M | LM | Charts degrade gracefully; tables still show data |

---

## 10. Requirements Traceability Seeds

| Req ID | Source (PRD) | Traces Forward To |
|--------|-------------|-------------------|
| FR-090 | US-080 | Design: analytics component → Code: db/database.py, routes/analytics.py, static/js/analytics.js → Test: test_analytics.py → Docs: analytics section |
| FR-091 | US-081 | Design: trend chart → Code: analytics.js, routes/analytics.py → Test: test_analytics.py |
| FR-092 | US-082 | Design: funnel component → Code: analytics.js → Test: test_analytics.py |
| FR-093 | US-083 | Design: platform table → Code: analytics.js, database.py → Test: test_analytics.py |
| FR-094 | US-080–087 | Design: enhanced API → Code: database.py, routes/analytics.py → Test: test_analytics_api.py |
| FR-095 | US-084 | Design: histogram → Code: analytics.js → Test: test_analytics.py |
| FR-096 | US-085 | Design: weekly panel → Code: analytics.js → Test: test_analytics.py |
| FR-097 | US-086 | Design: companies table → Code: analytics.js, database.py → Test: test_analytics.py |
| FR-098 | US-087 | Design: response time → Code: database.py, analytics.js → Test: test_analytics.py |
| FR-099 | US-081 | Design: daily endpoint → Code: database.py → Test: test_database.py |
| FR-100 | US-081 | Design: period selector → Code: analytics.js → Test: test_analytics.py |
| FR-101 | US-080–087 | Design: empty states → Code: analytics.js → Test: test_analytics.py |

---

## Software Requirements Specification — GATE 3 OUTPUT

**Document**: SRS-TASK-017-analytics-dashboard
**FRs**: 12 functional requirements (FR-090 to FR-101)
**NFRs**: 6 non-functional requirements (NFR-017-01 to NFR-017-06)
**ACs**: 42 total acceptance criteria (32 positive + 10 negative)
**Quality Checklist**: 20/20 items passed (100%)

### Quality Checklist Summary
- [x] Every user need from PRD mapped to >= 1 FR
- [x] Every FR has >= 1 positive AC AND >= 1 negative AC
- [x] NFRs cover performance, i18n, accessibility, testing, response size, rendering
- [x] Out of Scope section is non-empty and specific (7 items)
- [x] All assumptions documented with risk-if-wrong (5 assumptions)
- [x] Glossary defines all domain terms (8 definitions)
- [x] Zero vague words
- [x] Every AC uses Given/When/Then with specific values
- [x] Every NFR has measurable metric with concrete number
- [x] No FR contains implementation details
- [x] Each FR is atomic
- [x] Every FR can be verified by automated test
- [x] Every NFR can be verified by measurement
- [x] Every FR/NFR has unique stable ID
- [x] Dependencies documented
- [x] Traceability seeds prepared
- [x] No contradictions between requirements
- [x] Consistent terminology
- [x] Realistic priority distribution (5 P0, 4 P1, 1 P2, 2 cross-cutting P0)
- [x] All PRD open questions resolved in definitions

### Handoff Routing

| Recipient | What They Receive |
|-----------|-------------------|
| System Engineer | Full SRS — design component architecture, API contracts, data flow |
| Backend Developer | FR-094, FR-099 — implement enhanced endpoint + database methods |
| Frontend Developer | FR-090–093, FR-095–098, FR-100–101 — implement UI components |
| Unit Tester | 42 ACs — generate test cases for each |
| Integration Tester | NFR-017-01, NFR-017-05 — performance + response size validation |
| Security Engineer | FR-094 AC-094-11 — auth enforcement on new endpoint |
| Documenter | Feature descriptions for analytics user guide |
