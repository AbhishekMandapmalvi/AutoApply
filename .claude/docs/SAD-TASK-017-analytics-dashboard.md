# System Architecture Document

**Document ID**: SAD-TASK-017-analytics-dashboard
**Version**: 1.0
**Date**: 2026-03-11
**Status**: approved
**Author**: Claude (System Engineer)
**SRS Reference**: SRS-TASK-017-analytics-dashboard

---

## 1. Executive Summary

This architecture extends the existing Analytics module with a single consolidated
backend endpoint (`GET /api/analytics/enhanced`) that computes all metrics in one
database connection, and a restructured frontend analytics.js module that renders
8 visualization components using Chart.js. No schema changes, no new dependencies,
no new database tables. All data is derived from aggregate SQL queries on the existing
`applications` table.

---

## 2. Architecture Overview

### 2.1 Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Vanilla JS)                           │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                     analytics.js (extended)                       │  │
│  │                                                                   │  │
│  │  loadAnalytics(days=30)                                           │  │
│  │    ├── fetch('/api/analytics/enhanced?days=N')                     │  │
│  │    └── render all components:                                      │  │
│  │        ├── renderSummaryCards(data.summary)         [FR-090]       │  │
│  │        ├── renderPeriodSelector(activePeriod)       [FR-100]       │  │
│  │        ├── renderDailyChart(data.daily)             [FR-091]       │  │
│  │        ├── renderFunnelChart(data.funnel)           [FR-092]       │  │
│  │        ├── renderPlatformTable(data.platforms)      [FR-093]       │  │
│  │        ├── renderScoreChart(data.score_distribution)[FR-095]       │  │
│  │        ├── renderWeeklySummary(data.weekly)         [FR-096]       │  │
│  │        ├── renderTopCompanies(data.top_companies)   [FR-097]       │  │
│  │        └── renderResponseTimes(data.response_times) [FR-098]       │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│            │ fetch (Bearer token injected by auth.js)                  │
└────────────│───────────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     BACKEND (Flask Blueprint)                          │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                   routes/analytics.py                             │  │
│  │                                                                   │  │
│  │  GET /api/analytics/enhanced?days=N                  [FR-094]     │  │
│  │    ├── validate days param (int, >= 0, default 30)                │  │
│  │    ├── call db.get_enhanced_analytics(days)                       │  │
│  │    └── return jsonify(result)                                     │  │
│  │                                                                   │  │
│  │  GET /api/analytics/summary         (existing, unchanged)        │  │
│  │  GET /api/analytics/daily?days=N    (extended: days=0 = all)     │  │
│  │  GET /api/feed?limit=N              (existing, unchanged)        │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│            │                                                           │
└────────────│───────────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     DATABASE (db/database.py)                          │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │   Database.get_enhanced_analytics(days: int = 30) -> dict        │  │
│  │                                                                   │  │
│  │   Single connection, multiple queries:                            │  │
│  │     1. Summary: total, avg_score, this_week count                 │  │
│  │     2. Funnel: counts for applied/interview/offer statuses        │  │
│  │     3. Platform: GROUP BY platform with interview/offer counts    │  │
│  │     4. Score distribution: CASE WHEN bucketing + interview rates  │  │
│  │     5. Weekly: current vs previous 7-day window                   │  │
│  │     6. Top companies: GROUP BY company, top 10                    │  │
│  │     7. Response times: computed in Python from sorted days list   │  │
│  │     8. Daily: DATE(applied_at) GROUP BY with optional date filter │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│            │                                                           │
│            ▼                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │   applications table (no schema changes)                         │  │
│  │   Indexes: idx_applied_at, idx_status, idx_dedup                 │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow

1. User navigates to Analytics tab → `navigation.js` calls `loadAnalytics()`
2. `analytics.js` sends `GET /api/analytics/enhanced?days=30` with Bearer token
3. `routes/analytics.py` validates `days` parameter, calls `db.get_enhanced_analytics(30)`
4. `database.py` opens single SQLite connection, runs 8 aggregate queries sequentially
5. Python computes derived values (rates, medians) from raw query results
6. JSON response returned to frontend (~5-20 KB)
7. `analytics.js` renders 8 components into DOM using Chart.js + HTML tables
8. User clicks period selector → `loadAnalytics(newDays)` re-fetches and re-renders

### 2.3 Layer Architecture

| Layer | Component | Responsibility |
|-------|-----------|----------------|
| Presentation | `analytics.js` | Chart rendering, DOM manipulation, period selector UI |
| Presentation | `templates/index.html` | Analytics screen HTML structure (canvases, containers) |
| Presentation | `static/css/main.css` | Analytics layout styles |
| API | `routes/analytics.py` | HTTP endpoint, parameter validation, JSON serialization |
| Data Access | `db/database.py` | SQL queries, result aggregation, derived calculations |
| Storage | SQLite `applications` table | Raw application records |

---

## 3. Interface Contracts

### 3.1 Database.get_enhanced_analytics()

**Purpose**: Compute all analytics metrics in a single database connection.
**Category**: query (read-only)

**Signature**:

Input Parameters:
| Parameter | Type | Required | Constraints | Description |
|-----------|------|----------|-------------|-------------|
| days | int | no | default: 30, 0 = all time, must be >= 0 | Number of days to include in daily trend data |

Output:
| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| summary | dict | no | See §3.1.1 |
| funnel | dict | no | See §3.1.2 |
| platforms | list[dict] | no | See §3.1.3 (empty list if no data) |
| score_distribution | list[dict] | no | See §3.1.4 (always 10 elements) |
| weekly | dict | no | See §3.1.5 |
| top_companies | list[dict] | no | See §3.1.6 (up to 10 elements) |
| response_times | dict | no | See §3.1.7 |
| daily | list[dict] | no | See §3.1.8 (empty list if no data) |

**§3.1.1 summary**:
```json
{
  "total": 150,
  "interview_rate": 12.5,
  "avg_score": 72.3,
  "this_week": 18
}
```
- `total`: COUNT(*) of all applications (all statuses)
- `interview_rate`: `(interview_count / applied_count) * 100`, 1 decimal. 0.0 if no applied. Interview statuses: `{"interview", "interviewing", "interviewed"}`
- `avg_score`: AVG(match_score), 1 decimal. `null` if no applications
- `this_week`: COUNT where `applied_at >= date('now', 'weekday 1', '-7 days')` (ISO Monday start)

**§3.1.2 funnel**:
```json
{
  "applied": 120,
  "interview": 15,
  "offer": 3,
  "applied_to_interview_rate": 12.5,
  "interview_to_offer_rate": 20.0
}
```
- `applied`: COUNT where status IN ('applied', 'interview', 'interviewing', 'interviewed', 'offer', 'accepted') — all funnel-eligible
- `interview`: COUNT where status IN ('interview', 'interviewing', 'interviewed', 'offer', 'accepted') — reached interview or beyond
- `offer`: COUNT where status IN ('offer', 'accepted')
- Rates: percentage with 1 decimal, 0.0 if denominator is 0

**§3.1.3 platforms** (sorted by total DESC):
```json
[
  {
    "platform": "linkedin",
    "total": 80,
    "interviews": 5,
    "interview_rate": 6.3,
    "avg_score": 72.3,
    "offers": 1
  }
]
```

**§3.1.4 score_distribution** (always 10 buckets):
```json
[
  { "bucket": "0-9",   "count": 0, "interview_count": 0, "interview_rate": 0.0 },
  { "bucket": "10-19", "count": 2, "interview_count": 0, "interview_rate": 0.0 },
  ...
  { "bucket": "90-100","count": 8, "interview_count": 3, "interview_rate": 37.5 }
]
```
- Buckets: 0-9, 10-19, 20-29, 30-39, 40-49, 50-59, 60-69, 70-79, 80-89, 90-100
- `interview_count`: applications in this bucket with status IN interview statuses
- `interview_rate`: `(interview_count / count) * 100`, 1 decimal. 0.0 if count is 0

**§3.1.5 weekly**:
```json
{
  "current": { "applications": 25, "interviews": 3, "avg_score": 74.2 },
  "previous": { "applications": 20, "interviews": 5, "avg_score": 71.8 },
  "changes": { "applications": 5, "interviews": -2, "avg_score": 2.4 }
}
```
- Current week: `applied_at >= date('now', 'weekday 1', '-7 days')`
- Previous week: `applied_at >= date('now', 'weekday 1', '-14 days') AND applied_at < date('now', 'weekday 1', '-7 days')`
- `avg_score`: `null` if no applications in that period
- `changes.avg_score`: `null` if either period has `null` avg_score

**§3.1.6 top_companies** (up to 10, sorted by total DESC, then company ASC):
```json
[
  {
    "company": "Acme Corp",
    "total": 8,
    "statuses": { "applied": 5, "interview": 2, "rejected": 1 }
  }
]
```

**§3.1.7 response_times**:
```json
{
  "to_interview": { "median_days": 7.0, "avg_days": 8.2 },
  "to_rejected": { "median_days": 14.0, "avg_days": 12.5 }
}
```
- Computed from `JULIANDAY(updated_at) - JULIANDAY(applied_at)` for apps where status is in the target set AND status != 'applied'
- `to_interview`: status IN ('interview', 'interviewing', 'interviewed')
- `to_rejected`: status = 'rejected'
- Values are `null` if no applications match
- Median computed in Python: sort days list, take middle element (or avg of two middle for even count)
- Rounded to 1 decimal

**§3.1.8 daily** (same as existing `get_daily_analytics` but embedded):
```json
[
  { "date": "2026-03-01", "count": 5 },
  { "date": "2026-03-02", "count": 3 }
]
```
- Filtered by `days` parameter (0 = all time)
- Sorted by date ASC

**Errors**:
| Error Condition | Response |
|----------------|----------|
| days < 0 | Return default (30 days), no error — match existing Flask convention |
| Database not initialized | Caller (route) handles with 503 |

**Preconditions**: Database initialized, schema created.
**Postconditions**: No data modified. Read-only.
**Side Effects**: None.
**Idempotency**: Yes — pure query.
**Thread Safety**: Safe — each call creates its own connection via `_connect()`.
**Performance**: < 200ms for 10,000 rows (8 queries over single connection).

---

### 3.2 GET /api/analytics/enhanced

**Purpose**: HTTP endpoint returning all analytics data in one response.
**Category**: query

**Signature**:

Input Parameters (query string):
| Parameter | Type | Required | Constraints | Description |
|-----------|------|----------|-------------|-------------|
| days | int | no | default: 30, 0 = all time | Period for daily trend data |

Output (HTTP 200):
```json
{
  "summary": { ... },
  "funnel": { ... },
  "platforms": [ ... ],
  "score_distribution": [ ... ],
  "weekly": { ... },
  "top_companies": [ ... ],
  "response_times": { ... },
  "daily": [ ... ]
}
```
(Exact shapes defined in §3.1 sub-sections)

Errors:
| Error Condition | HTTP Status | Response |
|----------------|-------------|----------|
| Invalid/missing Bearer token | 401 | `{"error": "..."}` (handled by existing auth middleware) |
| Database not initialized | 503 | `{"error": "Database not initialized"}` |
| Non-integer `days` param | 200 | Uses default 30 (Flask type coercion) |

**Example**:
```
GET /api/analytics/enhanced?days=7
Authorization: Bearer abc123

HTTP 200
Content-Type: application/json
{
  "summary": { "total": 150, "interview_rate": 12.5, "avg_score": 72.3, "this_week": 18 },
  "funnel": { "applied": 120, "interview": 15, "offer": 3, "applied_to_interview_rate": 12.5, "interview_to_offer_rate": 20.0 },
  "platforms": [
    { "platform": "linkedin", "total": 80, "interviews": 5, "interview_rate": 6.3, "avg_score": 72.3, "offers": 1 },
    { "platform": "indeed", "total": 40, "interviews": 2, "interview_rate": 5.0, "avg_score": 68.1, "offers": 0 }
  ],
  "score_distribution": [
    { "bucket": "0-9", "count": 0, "interview_count": 0, "interview_rate": 0.0 },
    ...
  ],
  "weekly": {
    "current": { "applications": 18, "interviews": 2, "avg_score": 74.2 },
    "previous": { "applications": 15, "interviews": 3, "avg_score": 71.8 },
    "changes": { "applications": 3, "interviews": -1, "avg_score": 2.4 }
  },
  "top_companies": [
    { "company": "Acme Corp", "total": 8, "statuses": { "applied": 5, "interview": 2, "rejected": 1 } }
  ],
  "response_times": {
    "to_interview": { "median_days": 7.0, "avg_days": 8.2 },
    "to_rejected": { "median_days": 14.0, "avg_days": 12.5 }
  },
  "daily": [
    { "date": "2026-03-04", "count": 5 },
    { "date": "2026-03-05", "count": 3 }
  ]
}
```

---

### 3.3 GET /api/analytics/daily (extended)

**Purpose**: Existing endpoint, extended to support `days=0` for all-time data.
**Change**: When `days=0`, omit the WHERE clause date filter.

Input Parameters:
| Parameter | Type | Required | Constraints | Description |
|-----------|------|----------|-------------|-------------|
| days | int | no | default: 30, 0 = all time, negative treated as 30 | Period filter |

Output (HTTP 200): `[{"date": "YYYY-MM-DD", "count": N}, ...]`

---

### 3.4 Frontend: loadAnalytics(days)

**Purpose**: Fetch enhanced analytics and render all components.
**Category**: saga (orchestrates rendering)

**Signature**:

Input Parameters:
| Parameter | Type | Required | Constraints | Description |
|-----------|------|----------|-------------|-------------|
| days | int | no | default: 30 | Period preset (7, 30, 90, or 0) |

**Behavior**:
1. Set `activePeriod = days` in module state
2. Fetch `GET /api/analytics/enhanced?days=${days}`
3. On success: call all 8 render functions with appropriate data slices
4. On error: log warning, display error state in UI, retain previous charts

**Side Effects**: Destroys and recreates Chart.js instances. Updates DOM.

---

### 3.5 Frontend: Render Functions

All render functions follow the same pattern:

| Function | Input | Output (DOM) | Chart Type | FR |
|----------|-------|-------------|------------|-----|
| `renderSummaryCards(summary)` | summary object | 4 metric cards | HTML only | FR-090 |
| `renderPeriodSelector(activePeriod)` | int (7/30/90/0) | 4 toggle buttons | HTML only | FR-100 |
| `renderDailyChart(daily)` | array of {date, count} | Line chart | Chart.js line | FR-091 |
| `renderFunnelChart(funnel)` | funnel object | Horizontal bar | Chart.js bar | FR-092 |
| `renderPlatformTable(platforms)` | array of platform objects | Data table | HTML table | FR-093 |
| `renderScoreChart(scoreDistribution)` | array of 10 buckets | Stacked bar | Chart.js bar | FR-095 |
| `renderWeeklySummary(weekly)` | weekly object | Comparison panel | HTML only | FR-096 |
| `renderTopCompanies(topCompanies)` | array of company objects | Data table | HTML table | FR-097 |
| `renderResponseTimes(responseTimes)` | response_times object | Metric display | HTML only | FR-098 |

Each render function:
- Uses `t()` for all labels (NFR-017-02)
- Handles empty/null data gracefully (FR-101)
- Destroys previous Chart.js instance before recreating (prevent memory leaks)

---

## 4. Data Model

### 4.1 No New Entities

All analytics are derived from the existing `applications` table. No new tables,
columns, or indexes required.

### 4.2 Query Designs

#### Q1: Summary Metrics
```sql
-- Total applications
SELECT COUNT(*) as total FROM applications;

-- Average match score
SELECT AVG(match_score) as avg_score FROM applications;

-- This week count (ISO Monday start)
SELECT COUNT(*) as this_week FROM applications
WHERE applied_at >= date('now', 'weekday 1', '-7 days');

-- Interview count (for rate calculation)
SELECT COUNT(*) as interview_count FROM applications
WHERE status IN ('interview', 'interviewing', 'interviewed');

-- Applied count (denominator for interview rate)
SELECT COUNT(*) as applied_count FROM applications
WHERE status = 'applied';
```

#### Q2: Funnel Counts
```sql
-- Funnel-eligible (applied + made progress)
SELECT
  COUNT(*) FILTER (WHERE status IN ('applied','interview','interviewing','interviewed','offer','accepted')) as funnel_applied,
  COUNT(*) FILTER (WHERE status IN ('interview','interviewing','interviewed','offer','accepted')) as funnel_interview,
  COUNT(*) FILTER (WHERE status IN ('offer','accepted')) as funnel_offer
FROM applications;
```
Note: SQLite does not support FILTER. Use SUM(CASE WHEN ... THEN 1 ELSE 0 END):
```sql
SELECT
  SUM(CASE WHEN status IN ('applied','interview','interviewing','interviewed','offer','accepted') THEN 1 ELSE 0 END) as funnel_applied,
  SUM(CASE WHEN status IN ('interview','interviewing','interviewed','offer','accepted') THEN 1 ELSE 0 END) as funnel_interview,
  SUM(CASE WHEN status IN ('offer','accepted') THEN 1 ELSE 0 END) as funnel_offer
FROM applications;
```

#### Q3: Platform Performance
```sql
SELECT
  platform,
  COUNT(*) as total,
  SUM(CASE WHEN status IN ('interview','interviewing','interviewed') THEN 1 ELSE 0 END) as interviews,
  ROUND(AVG(match_score), 1) as avg_score,
  SUM(CASE WHEN status IN ('offer','accepted') THEN 1 ELSE 0 END) as offers
FROM applications
GROUP BY platform
ORDER BY total DESC;
```

#### Q4: Score Distribution
```sql
SELECT
  CASE
    WHEN match_score BETWEEN 0  AND 9  THEN '0-9'
    WHEN match_score BETWEEN 10 AND 19 THEN '10-19'
    WHEN match_score BETWEEN 20 AND 29 THEN '20-29'
    WHEN match_score BETWEEN 30 AND 39 THEN '30-39'
    WHEN match_score BETWEEN 40 AND 49 THEN '40-49'
    WHEN match_score BETWEEN 50 AND 59 THEN '50-59'
    WHEN match_score BETWEEN 60 AND 69 THEN '60-69'
    WHEN match_score BETWEEN 70 AND 79 THEN '70-79'
    WHEN match_score BETWEEN 80 AND 89 THEN '80-89'
    ELSE '90-100'
  END as bucket,
  COUNT(*) as count,
  SUM(CASE WHEN status IN ('interview','interviewing','interviewed') THEN 1 ELSE 0 END) as interview_count
FROM applications
GROUP BY bucket
ORDER BY MIN(match_score);
```
Note: Empty buckets must be filled in Python (SQL only returns buckets with data).

#### Q5: Weekly Comparison
```sql
-- Current week
SELECT COUNT(*) as applications,
  SUM(CASE WHEN status IN ('interview','interviewing','interviewed') THEN 1 ELSE 0 END) as interviews,
  ROUND(AVG(match_score), 1) as avg_score
FROM applications
WHERE applied_at >= date('now', 'weekday 1', '-7 days');

-- Previous week
SELECT COUNT(*) as applications,
  SUM(CASE WHEN status IN ('interview','interviewing','interviewed') THEN 1 ELSE 0 END) as interviews,
  ROUND(AVG(match_score), 1) as avg_score
FROM applications
WHERE applied_at >= date('now', 'weekday 1', '-14 days')
  AND applied_at < date('now', 'weekday 1', '-7 days');
```

#### Q6: Top Companies
```sql
SELECT company, COUNT(*) as total
FROM applications
GROUP BY company
ORDER BY total DESC, company ASC
LIMIT 10;
```
Status breakdown per company (separate query or subquery):
```sql
SELECT company, status, COUNT(*) as count
FROM applications
WHERE company IN (/* top 10 companies */)
GROUP BY company, status;
```

#### Q7: Response Times
```sql
-- To interview
SELECT JULIANDAY(updated_at) - JULIANDAY(applied_at) as days_to_respond
FROM applications
WHERE status IN ('interview', 'interviewing', 'interviewed')
  AND updated_at != applied_at
ORDER BY days_to_respond;

-- To rejected
SELECT JULIANDAY(updated_at) - JULIANDAY(applied_at) as days_to_respond
FROM applications
WHERE status = 'rejected'
  AND updated_at != applied_at
ORDER BY days_to_respond;
```
Median computed in Python from the sorted list.

#### Q8: Daily Trend
Reuses existing `get_daily_analytics` logic with `days=0` support.

---

## 5. Error Handling Strategy

| Error | Layer | Handling |
|-------|-------|----------|
| Database not initialized | Route | Return 503 via existing `_get_db()` pattern |
| Zero denominator in rate calc | Database method | Return 0.0 (not NaN, not error) |
| No data for response times | Database method | Return `null` for median/avg |
| Chart.js not loaded | Frontend | Check `typeof Chart !== 'undefined'`, show error |
| API fetch failure | Frontend | `console.warn()`, show error state in UI, retain previous data |
| Non-integer days param | Route | Flask `request.args.get('days', 30, type=int)` silently defaults to 30 |

---

## 6. Frontend Layout Design

### 6.1 HTML Structure (screen-analytics replacement)

```html
<div class="screen hidden" id="screen-analytics">
  <h2 data-i18n="analytics.screen_title">Analytics</h2>

  <!-- Summary Cards (FR-090) -->
  <div class="analytics-summary-cards" id="analytics-summary">
    <!-- 4 cards rendered by JS -->
  </div>

  <!-- Period Selector (FR-100) -->
  <div class="analytics-period-selector" role="group" aria-label="Time period">
    <button class="period-btn active" data-days="7" data-i18n="analytics.period_7d">7d</button>
    <button class="period-btn" data-days="30" data-i18n="analytics.period_30d">30d</button>
    <button class="period-btn" data-days="90" data-i18n="analytics.period_90d">90d</button>
    <button class="period-btn" data-days="0" data-i18n="analytics.period_all">All</button>
  </div>

  <!-- Trend Chart (FR-091) -->
  <div class="card"><h3 data-i18n="analytics.chart_daily_title">...</h3>
    <div class="chart-container"><canvas id="chart-daily"></canvas></div>
  </div>

  <!-- Two-column: Funnel + Platform Table -->
  <div class="analytics-grid">
    <div class="card"><h3 data-i18n="analytics.funnel_title">...</h3>
      <div class="chart-container"><canvas id="chart-funnel"></canvas></div>
    </div>
    <div class="card"><h3 data-i18n="analytics.platform_title">...</h3>
      <div id="platform-table-container"><!-- table rendered by JS --></div>
    </div>
  </div>

  <!-- Two-column: Score Distribution + Weekly Summary -->
  <div class="analytics-grid">
    <div class="card"><h3 data-i18n="analytics.score_title">...</h3>
      <div class="chart-container"><canvas id="chart-score"></canvas></div>
    </div>
    <div class="card"><h3 data-i18n="analytics.weekly_title">...</h3>
      <div id="weekly-summary-container"><!-- rendered by JS --></div>
    </div>
  </div>

  <!-- Two-column: Top Companies + Response Times -->
  <div class="analytics-grid">
    <div class="card"><h3 data-i18n="analytics.companies_title">...</h3>
      <div id="top-companies-container"><!-- table rendered by JS --></div>
    </div>
    <div class="card"><h3 data-i18n="analytics.response_title">...</h3>
      <div id="response-times-container"><!-- rendered by JS --></div>
    </div>
  </div>
</div>
```

### 6.2 CSS Additions (appended to main.css)

```css
/* Summary cards row */
.analytics-summary-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}
.analytics-summary-cards .summary-card {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px;
  text-align: center;
}
.summary-card .summary-value {
  font-size: 2rem;
  font-weight: 700;
  color: var(--text-bright);
}
.summary-card .summary-label {
  color: var(--text-dim);
  font-size: 0.85rem;
  margin-top: 4px;
}

/* Period selector */
.analytics-period-selector {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
}
.period-btn {
  padding: 6px 16px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--panel);
  color: var(--text-dim);
  cursor: pointer;
}
.period-btn.active {
  background: var(--accent);
  color: var(--text-bright);
  border-color: var(--accent);
}
.period-btn:focus-visible {
  outline: 2px solid var(--info);
  outline-offset: 2px;
}

/* Responsive: summary cards collapse to 2x2 on small screens */
@media (max-width: 768px) {
  .analytics-summary-cards { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 480px) {
  .analytics-summary-cards { grid-template-columns: 1fr; }
}

/* Trend indicator arrows */
.trend-up { color: var(--success); }
.trend-down { color: var(--danger); }
.trend-neutral { color: var(--text-dim); }
```

### 6.3 i18n Keys (additions to en.json analytics section)

```json
{
  "analytics": {
    "applications_label": "Applications",
    "screen_title": "Analytics",
    "chart_daily_title": "Applications Over Time",
    "chart_status_title": "Status Breakdown",
    "chart_platform_title": "By Platform",
    "period_7d": "7d",
    "period_30d": "30d",
    "period_90d": "90d",
    "period_all": "All",
    "summary_total": "Total Applications",
    "summary_interview_rate": "Interview Rate",
    "summary_avg_score": "Avg Match Score",
    "summary_this_week": "This Week",
    "funnel_title": "Conversion Funnel",
    "funnel_applied": "Applied",
    "funnel_interview": "Interview",
    "funnel_offer": "Offer",
    "platform_title": "Platform Performance",
    "platform_col_name": "Platform",
    "platform_col_total": "Total",
    "platform_col_interviews": "Interviews",
    "platform_col_rate": "Rate",
    "platform_col_avg_score": "Avg Score",
    "platform_col_offers": "Offers",
    "score_title": "Score Distribution",
    "score_tooltip_interviews": "{count} interviews ({rate}%)",
    "weekly_title": "Weekly Summary",
    "weekly_current": "This Week",
    "weekly_previous": "Last Week",
    "weekly_change": "Change",
    "weekly_applications": "Applications",
    "weekly_interviews": "Interviews",
    "weekly_avg_score": "Avg Score",
    "companies_title": "Top Companies",
    "companies_col_name": "Company",
    "companies_col_total": "Total",
    "companies_col_statuses": "Status Breakdown",
    "response_title": "Response Times",
    "response_to_interview": "To Interview",
    "response_to_rejected": "To Rejected",
    "response_median": "Median",
    "response_average": "Average",
    "response_days": "{days} days",
    "empty_state": "No application data yet. Start the bot to begin tracking analytics.",
    "error_loading": "Could not load analytics data."
  }
}
```

---

## 7. Architecture Decision Records

### ADR-021: Single Enhanced Endpoint vs. Multiple Granular Endpoints

**Status**: accepted

**Context**: The analytics dashboard requires 8 types of data. We could either (a) create
8 separate endpoints, or (b) create a single endpoint returning all data.

**Decision**: Single endpoint `GET /api/analytics/enhanced` returning all data.

**Alternatives Considered**:

| Option | Pros | Cons |
|--------|------|------|
| 8 separate endpoints | Granular caching, independent loading | 8 HTTP round-trips, 8 DB connections, complex frontend orchestration |
| **Single endpoint** | **1 round-trip, 1 DB connection, simpler frontend** | **Larger response, all-or-nothing loading** |

**Consequences**:
- Positive: Single fetch, single connection, simpler error handling, ~5-20 KB response
- Negative: Cannot cache individual metrics independently
- Risks: If one query is slow, it delays the entire response → mitigated by SQLite speed on indexed queries

**Rationale**: For a local desktop app with SQLite, network latency is negligible. A single
connection with 8 sequential queries is faster than 8 separate connections. Response size
is small. Frontend code is simpler with a single fetch.

---

## 8. Design Traceability Matrix

| Requirement | Type | Design Component(s) | Interface(s) | ADR |
|-------------|------|---------------------|---------------|-----|
| FR-090 | FR | analytics.js `renderSummaryCards()`, index.html | `get_enhanced_analytics().summary` | — |
| FR-091 | FR | analytics.js `renderDailyChart()`, index.html | `get_enhanced_analytics().daily` | — |
| FR-092 | FR | analytics.js `renderFunnelChart()`, index.html | `get_enhanced_analytics().funnel` | — |
| FR-093 | FR | analytics.js `renderPlatformTable()`, index.html | `get_enhanced_analytics().platforms` | — |
| FR-094 | FR | routes/analytics.py, db/database.py | `GET /api/analytics/enhanced`, `Database.get_enhanced_analytics()` | ADR-021 |
| FR-095 | FR | analytics.js `renderScoreChart()`, index.html | `get_enhanced_analytics().score_distribution` | — |
| FR-096 | FR | analytics.js `renderWeeklySummary()`, index.html | `get_enhanced_analytics().weekly` | — |
| FR-097 | FR | analytics.js `renderTopCompanies()`, index.html | `get_enhanced_analytics().top_companies` | — |
| FR-098 | FR | analytics.js `renderResponseTimes()`, index.html | `get_enhanced_analytics().response_times` | — |
| FR-099 | FR | db/database.py `get_daily_analytics()` | Extended: `days=0` support | — |
| FR-100 | FR | analytics.js `renderPeriodSelector()`, index.html, main.css | Period button click → `loadAnalytics(days)` | — |
| FR-101 | FR | analytics.js (all render functions) | Empty state checks in each function | — |
| NFR-017-01 | NFR | db/database.py `get_enhanced_analytics()` | Single connection, indexed queries | ADR-021 |
| NFR-017-02 | NFR | analytics.js (all render functions), index.html | `t()` calls, `data-i18n` attributes | — |
| NFR-017-03 | NFR | index.html, analytics.js, main.css | ARIA attributes, keyboard nav, semantic HTML | — |
| NFR-017-04 | NFR | tests/test_analytics_enhanced.py | pytest coverage >= 80% | — |
| NFR-017-05 | NFR | routes/analytics.py | Response size validation | ADR-021 |
| NFR-017-06 | NFR | analytics.js | Chart.js rendering optimization | — |

**Completeness**: 18/18 requirements mapped (12 FR + 6 NFR). Zero gaps.

---

## 9. Implementation Plan

| Order | Task ID | Description | Depends On | Size | Files | FR Coverage |
|-------|---------|-------------|------------|------|-------|-------------|
| 1 | IMPL-017-01 | Add `get_enhanced_analytics()` to `db/database.py` | — | M | db/database.py | FR-094, FR-099 |
| 2 | IMPL-017-02 | Add `GET /api/analytics/enhanced` route | IMPL-017-01 | S | routes/analytics.py | FR-094 |
| 3 | IMPL-017-03 | Extend `get_daily_analytics()` for `days=0` | — | S | db/database.py | FR-099 |
| 4 | IMPL-017-04 | Add i18n keys to `en.json` | — | S | static/locales/en.json | NFR-017-02 |
| 5 | IMPL-017-05 | Update analytics HTML in `index.html` | IMPL-017-04 | M | templates/index.html | FR-090–FR-101 |
| 6 | IMPL-017-06 | Add analytics CSS to `main.css` | — | S | static/css/main.css | NFR-017-03 |
| 7 | IMPL-017-07 | Rewrite `analytics.js` with all render functions | IMPL-017-04, IMPL-017-05 | L | static/js/analytics.js | FR-090–FR-101 |
| 8 | IMPL-017-08 | Write unit tests for `get_enhanced_analytics()` | IMPL-017-01 | M | tests/test_analytics_enhanced.py | NFR-017-04 |
| 9 | IMPL-017-09 | Write integration tests for enhanced endpoint | IMPL-017-02 | S | tests/test_analytics_enhanced.py | NFR-017-04, NFR-017-01 |

### Per-Task Detail

#### IMPL-017-01: Database — get_enhanced_analytics()
- **Modifies**: `db/database.py`
- **Adds**: `get_enhanced_analytics(days: int = 30) -> dict` method to Database class
- **Runs**: 8 SQL queries in single `_connect()` context
- **Computes**: Rates, medians in Python from query results
- **Done when**: Method returns correct JSON-serializable dict matching §3.1 contract

#### IMPL-017-02: Route — GET /api/analytics/enhanced
- **Modifies**: `routes/analytics.py`
- **Adds**: New route function calling `db.get_enhanced_analytics(days)`
- **Pattern**: Same as existing `analytics_summary()` — `_get_db()`, validate params, `jsonify()`
- **Done when**: Endpoint returns correct JSON per §3.2

#### IMPL-017-03: Database — extend get_daily_analytics()
- **Modifies**: `db/database.py` method `get_daily_analytics()`
- **Change**: When `days <= 0`, omit WHERE clause date filter
- **Done when**: `get_daily_analytics(0)` returns all-time data

#### IMPL-017-04: i18n — analytics locale keys
- **Modifies**: `static/locales/en.json`
- **Adds**: ~30 new keys under `analytics` section (per §6.3)
- **Done when**: All keys from §6.3 present in en.json

#### IMPL-017-05: HTML — analytics screen restructure
- **Modifies**: `templates/index.html`
- **Replaces**: Existing `screen-analytics` div with new layout (per §6.1)
- **Adds**: Summary cards container, period selector, funnel canvas, table containers
- **Preserves**: `chart-daily` canvas ID (existing), adds new IDs
- **Done when**: All container elements present with `data-i18n` attributes

#### IMPL-017-06: CSS — analytics styles
- **Modifies**: `static/css/main.css`
- **Adds**: Summary cards grid, period selector styles, trend indicators (per §6.2)
- **Done when**: Summary cards render in 4-column grid, period buttons styled

#### IMPL-017-07: Frontend — analytics.js rewrite
- **Modifies**: `static/js/analytics.js`
- **Replaces**: Existing 3 render functions with 9 functions + `loadAnalytics(days)`
- **Preserves**: `chartInstances` pattern, `t()` usage, `export async function loadAnalytics()`
- **Adds**: Period selector click handler (exposed on `window` for onclick)
- **Done when**: All 8 visualizations render from enhanced endpoint data

#### IMPL-017-08: Unit tests — database method
- **Creates**: `tests/test_analytics_enhanced.py`
- **Tests**: `get_enhanced_analytics()` with various data scenarios:
  - Empty database, single application, many applications
  - All status types, all platforms
  - Score distribution edge cases (score=0, score=100)
  - Weekly with zero data in previous week
  - Response times with null transitions
  - Performance test with 10,000 rows (< 200ms)
- **Done when**: >= 80% coverage on new database code, all assertions pass

#### IMPL-017-09: Integration tests — API endpoint
- **Modifies** or **extends**: `tests/test_analytics_enhanced.py`
- **Tests**: HTTP-level tests for `GET /api/analytics/enhanced`:
  - Default params, custom days, days=0
  - Response shape validation (all keys present)
  - Empty database response
  - Auth enforcement (401 without token — if not bypassed in test)
- **Done when**: All endpoint contracts verified

---

## System Architecture — GATE 4 OUTPUT

**Document**: SAD-TASK-017-analytics-dashboard
**Components**: 5 components (database method, API route, analytics.js, index.html, main.css)
**Interfaces**: 5 contracts specified (§3.1–§3.5)
**Entities**: 0 new entities (uses existing `applications` table)
**ADRs**: 1 decision documented (ADR-021)
**Impl Tasks**: 9 tasks in dependency order
**Traceability**: 18/18 requirements mapped (100%)
**Checklist**: 20/20 items passed

### Handoff Routing

| Recipient | What They Receive |
|-----------|-------------------|
| Backend Developer | §3.1–§3.3 interface contracts, §4.2 query designs, IMPL-017-01/02/03 |
| Frontend Developer | §3.4–§3.5 render contracts, §6.1–§6.3 layout/CSS/i18n, IMPL-017-04/05/06/07 |
| Unit Tester | §3.1 output contracts for test generation, IMPL-017-08 |
| Integration Tester | §3.2 API contract for endpoint tests, IMPL-017-09 |
| Security Engineer | §3.2 auth enforcement (existing middleware applies) |
| Documenter | Feature description for analytics user guide |
