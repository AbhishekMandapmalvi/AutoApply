# Product Requirements Document

**Feature**: Analytics Dashboard
**Date**: 2026-03-11
**Author**: Claude (Product Manager)
**Status**: approved
**Version Target**: v2.0.0

---

## 1. Problem Statement

### What problem are we solving?
Users submit dozens to hundreds of job applications through AutoApply but have no way
to understand their application performance. They cannot answer: "Which platforms give
me the best response rate?", "Is my match score threshold too high or low?",
"What's my interview conversion rate?", or "Am I applying to enough jobs per week?"

### Who has this problem?
Active AutoApply users who have accumulated 20+ applications and want to optimize
their job search strategy.

### How big is this problem?
Every active user. Without analytics, users operate blindly — they cannot tell if
their configuration (score threshold, platforms, keywords) is effective or needs tuning.

### How is it solved today?
The existing Analytics screen shows 3 basic Chart.js charts (daily line, status doughnut,
platform bar) using two endpoints (`/api/analytics/summary`, `/api/analytics/daily`).
These provide raw counts but no conversion rates, trends, response tracking, score
analysis, or actionable insights. Users must mentally compute ratios.

---

## 2. User Personas

| Persona          | Description                          | Key Need                        | Pain Point                                | Frequency |
|------------------|--------------------------------------|---------------------------------|-------------------------------------------|-----------|
| Active Searcher  | Uses bot daily, 50+ apps/week        | Optimize strategy in real-time  | Can't tell which platform converts best   | Daily     |
| Periodic Reviewer| Checks dashboard weekly              | Weekly progress summary         | No week-over-week trend comparison        | Weekly    |
| Strategy Tuner   | Adjusts config based on results      | Data-driven config decisions    | No correlation between score and outcomes | Monthly   |

---

## 3. User Stories

| ID     | As a...           | I want to...                                        | So that...                                           | Priority | Size |
|--------|--------------------|-----------------------------------------------------|------------------------------------------------------|----------|------|
| US-080 | Active Searcher    | See key metrics at a glance (total, rate, avg score) | I know my overall application health instantly        | P0       | M    |
| US-081 | Active Searcher    | View application trends over configurable periods    | I can see if my pace is increasing or declining       | P0       | M    |
| US-082 | Active Searcher    | See conversion rates by status (applied→interview)   | I know my interview hit rate                          | P0       | S    |
| US-083 | Strategy Tuner     | See success rates broken down by platform            | I can focus on platforms that convert best            | P0       | M    |
| US-084 | Strategy Tuner     | Analyze match score distribution vs outcomes         | I can tune my min_match_score threshold               | P1       | M    |
| US-085 | Periodic Reviewer  | See a weekly summary with period-over-period change  | I can track my progress week-over-week                | P1       | M    |
| US-086 | Active Searcher    | See top companies by application count               | I know if I'm over-applying to the same companies     | P1       | S    |
| US-087 | Active Searcher    | See a response time estimate (applied→status change) | I know how long companies typically take to respond   | P2       | M    |

### Acceptance Criteria

#### US-080: Key Metrics Summary Cards
- Given I navigate to the Analytics screen, When the page loads, Then I see summary cards showing: total applications, interview rate (%), average match score, and applications this week
- Given there are zero applications, When I view Analytics, Then all cards show 0 or "—" with an empty state message

#### US-081: Application Trend Chart
- Given I have applications over 30+ days, When I view the trend chart, Then I see a line chart with daily counts
- Given I select a different period (7d, 30d, 90d, all), When the chart reloads, Then it shows data for that period only

#### US-082: Status Conversion Funnel
- Given I have applications in multiple statuses, When I view the funnel, Then I see: Applied → Interview → Offer with percentage conversion at each step
- Given I have 100 applied, 10 interview, 2 offer, When I view funnel, Then I see 10% and 20% conversion rates

#### US-083: Platform Performance Table
- Given I have applications across multiple platforms, When I view platform breakdown, Then I see a table with: platform name, total apps, interview count, interview rate, avg match score
- Given a platform has zero interviews, When displayed, Then interview rate shows "0%"

#### US-084: Score Distribution Chart
- Given I have applications with varying match scores, When I view score analysis, Then I see a histogram of scores in 10-point buckets (0-10, 11-20, ..., 91-100)
- Given I can see score buckets, When I look at each bucket, Then I see the count and the interview rate for that bucket

#### US-085: Weekly Summary with Trends
- Given I have 2+ weeks of data, When I view weekly summary, Then I see this week vs last week: apps count, interviews, avg score, with up/down arrows and % change

#### US-086: Top Companies
- Given I have applied to multiple companies, When I view top companies, Then I see the top 10 companies by application count with status breakdown

#### US-087: Response Time Metrics
- Given applications have transitioned from "applied" to "interview" or "rejected", When I view response time, Then I see median and average days between applied_at and updated_at for each transition

---

## 4. Success Metrics

| Metric                    | Current Baseline     | Target                  | Measurement Method         | Timeline    |
|---------------------------|----------------------|-------------------------|----------------------------|-------------|
| Analytics screen usage    | Basic (3 charts)     | Rich (8+ visualizations)| Feature completeness       | v2.0.0      |
| Data queries < 200ms      | ~50ms (2 queries)    | < 200ms (8 queries)     | Backend response time      | v2.0.0      |
| User can answer "which platform converts best?" | No | Yes                  | Feature exists             | v2.0.0      |
| Test coverage             | N/A                  | > 80% on new code       | pytest coverage report     | v2.0.0      |

---

## 5. Scope

### In Scope (this release)
- Summary metric cards (US-080)
- Configurable trend chart with period selector (US-081)
- Status conversion funnel display (US-082)
- Platform performance comparison table (US-083)
- Match score distribution histogram (US-084)
- Weekly summary with period-over-period change (US-085)
- Top companies breakdown (US-086)
- Response time metrics (US-087)
- Backend API endpoints for all new analytics queries
- i18n for all new UI strings
- Accessibility (ARIA, keyboard nav) for all new components
- Unit + integration tests for all new code

### Out of Scope (explicitly excluded)
- Export analytics to PDF/CSV — Reason: deferred to v2.1.0
- Goal setting / target tracking — Reason: separate feature
- Email/notification digest — Reason: no notification system exists
- AI-powered insights ("you should apply more to LinkedIn") — Reason: v2.1.0
- Comparison with external benchmarks — Reason: no external data available

### Future Considerations (backlog)
- Analytics export (PDF report, CSV data)
- Custom date range picker (beyond 7d/30d/90d/all presets)
- Salary analysis (requires structured salary data)
- Geographic heatmap of applications

---

## 6. Prioritization (MoSCoW)

- **Must have** (60% effort): US-080 (summary cards), US-081 (trend chart), US-082 (funnel), US-083 (platform table)
- **Should have** (20% effort): US-084 (score distribution), US-085 (weekly summary)
- **Could have** (15% effort): US-086 (top companies), US-087 (response time)
- **Won't have** (0%): Export, AI insights, goal tracking

---

## 7. Constraints
- Must use existing SQLite database — no schema changes (all data already captured)
- Must use Chart.js (already bundled) — no new charting dependencies
- Must follow vanilla JS ES module pattern (no build step)
- All strings through i18n (`t()` / `data-i18n`)
- All UI components WCAG 2.1 AA accessible
- Backend endpoints must be < 200ms for up to 10,000 applications

## 8. Risks
| Risk | Probability | Impact | Mitigation |
|------|:-----------:|:------:|------------|
| Query performance on large datasets | L | M | Index on applied_at already exists; add query EXPLAIN analysis |
| Chart.js rendering slow with many data points | L | L | Aggregate to daily/weekly buckets, limit to 365 data points |
| Complex SQL for conversion rates | M | L | Test with edge cases (zero denominator, null dates) |
| Frontend module getting too large | M | M | analytics.js already exists; extend it, split if > 400 LOC |

## 9. Open Questions
| # | Question | Needed By | Status |
|---|----------|-----------|--------|
| 1 | Should "interview" and "interviewing" and "interviewed" all count as interview conversions? | Phase 3 (Requirements) | resolved: yes, all three |
| 2 | Should error/skipped/manual_required count in total applications or be excluded? | Phase 3 | resolved: include all, but conversion funnel starts from "applied" only |
| 3 | What period presets? | Phase 3 | resolved: 7d, 30d, 90d, all |

---

## Product Vision — GATE 2 OUTPUT

**Document**: PRD-TASK-017
**User Stories**: 8 stories (4 P0, 2 P1, 2 P2)
**Success Metrics**: 4 defined with baselines
**Scope**: bounded (in/out/future defined)

### Handoff
→ Requirements Analyst: PRD + user stories for formal SRS
→ Project Manager: scope + priorities for planning
→ System Engineer: stories + constraints for feasibility
