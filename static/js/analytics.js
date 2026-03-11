/* ═══════════════════════════════════════════════════════════════
   ANALYTICS DASHBOARD
   Implements: FR-090 to FR-101 (Analytics Dashboard v2.0.0)
   ═══════════════════════════════════════════════════════════════ */
import { t } from './i18n.js';
import { escHtml } from './helpers.js';

let chartInstances = {};
let activePeriod = 30;

/* ── Main entry point ─────────────────────────────────────────── */

export async function loadAnalytics(days) {
  if (days !== undefined) activePeriod = days;
  try {
    const res = await fetch(`/api/analytics/enhanced?days=${activePeriod}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    renderSummaryCards(data.summary);
    renderPeriodSelector(activePeriod);
    renderDailyChart(data.daily);
    renderFunnelChart(data.funnel);
    renderPlatformTable(data.platforms);
    renderScoreChart(data.score_distribution);
    renderWeeklySummary(data.weekly);
    renderTopCompanies(data.top_companies);
    renderResponseTimes(data.response_times);
  } catch (e) {
    console.warn('Could not load analytics:', e);
  }
}

/* ── Period Selector (FR-100) ────────────────────────────────── */

export function switchAnalyticsPeriod(days) {
  loadAnalytics(days);
}

function renderPeriodSelector(active) {
  const btns = document.querySelectorAll('.period-btn');
  btns.forEach(btn => {
    const d = parseInt(btn.getAttribute('data-days'), 10);
    btn.classList.toggle('active', d === active);
    btn.setAttribute('aria-pressed', d === active ? 'true' : 'false');
  });
}

/* ── Summary Cards (FR-090) ──────────────────────────────────── */

function renderSummaryCards(summary) {
  const el = (id, val) => {
    const node = document.getElementById(id);
    if (node) node.textContent = val;
  };
  el('summary-total', summary.total);
  el('summary-interview-rate', summary.interview_rate != null ? summary.interview_rate + '%' : '—');
  el('summary-avg-score', summary.avg_score != null ? summary.avg_score : '—');
  el('summary-this-week', summary.this_week);
}

/* ── Daily Trend Chart (FR-091) ──────────────────────────────── */

function renderDailyChart(data) {
  const ctx = document.getElementById('chart-daily');
  if (!ctx) return;
  if (chartInstances.daily) chartInstances.daily.destroy();

  if (!data || data.length === 0) {
    _showEmpty(ctx.parentNode);
    return;
  }

  chartInstances.daily = new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.map(d => d.date),
      datasets: [{
        label: t('analytics.applications_label'),
        data: data.map(d => d.count),
        borderColor: '#4da6ff',
        backgroundColor: 'rgba(77,166,255,.1)',
        tension: 0.4,
        fill: true,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#8892a4', maxTicksLimit: 10 }, grid: { color: 'rgba(255,255,255,.05)' } },
        y: { ticks: { color: '#8892a4', stepSize: 1 }, grid: { color: 'rgba(255,255,255,.05)' }, beginAtZero: true },
      },
    },
  });
}

/* ── Conversion Funnel (FR-092) ──────────────────────────────── */

function renderFunnelChart(funnel) {
  const ctx = document.getElementById('chart-funnel');
  if (!ctx) return;
  if (chartInstances.funnel) chartInstances.funnel.destroy();

  const labels = [
    t('analytics.funnel_applied'),
    t('analytics.funnel_interview'),
    t('analytics.funnel_offer'),
  ];
  const values = [funnel.applied, funnel.interview, funnel.offer];
  const colors = ['#4da6ff', '#53d769', '#ffc107'];

  chartInstances.funnel = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: colors,
        borderRadius: 6,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            afterLabel: (ctx) => {
              if (ctx.dataIndex === 0) return '';
              if (ctx.dataIndex === 1) return funnel.applied_to_interview_rate + '%';
              if (ctx.dataIndex === 2) return funnel.interview_to_offer_rate + '%';
              return '';
            }
          }
        }
      },
      scales: {
        x: { ticks: { color: '#8892a4', stepSize: 1 }, grid: { color: 'rgba(255,255,255,.05)' }, beginAtZero: true },
        y: { ticks: { color: '#8892a4' }, grid: { display: false } },
      },
    },
  });
}

/* ── Platform Performance Table (FR-093) ─────────────────────── */

function renderPlatformTable(platforms) {
  const container = document.getElementById('platform-table-container');
  if (!container) return;

  if (!platforms || platforms.length === 0) {
    container.innerHTML = `<div class="analytics-empty">${escHtml(t('analytics.empty_state'))}</div>`;
    return;
  }

  const hName = escHtml(t('analytics.platform_col_name'));
  const hTotal = escHtml(t('analytics.platform_col_total'));
  const hInterviews = escHtml(t('analytics.platform_col_interviews'));
  const hRate = escHtml(t('analytics.platform_col_rate'));
  const hScore = escHtml(t('analytics.platform_col_avg_score'));
  const hOffers = escHtml(t('analytics.platform_col_offers'));

  let html = `<table class="analytics-table" role="table">
    <thead><tr>
      <th scope="col">${hName}</th><th scope="col">${hTotal}</th>
      <th scope="col">${hInterviews}</th><th scope="col">${hRate}</th>
      <th scope="col">${hScore}</th><th scope="col">${hOffers}</th>
    </tr></thead><tbody>`;

  for (const p of platforms) {
    html += `<tr>
      <td>${escHtml(_capitalize(p.platform))}</td>
      <td>${p.total}</td><td>${p.interviews}</td>
      <td>${p.interview_rate}%</td><td>${p.avg_score}</td>
      <td>${p.offers}</td></tr>`;
  }
  html += '</tbody></table>';
  container.innerHTML = html;
}

/* ── Score Distribution Chart (FR-095) ───────────────────────── */

function renderScoreChart(scoreDistribution) {
  const ctx = document.getElementById('chart-score');
  if (!ctx) return;
  if (chartInstances.score) chartInstances.score.destroy();

  const labels = scoreDistribution.map(b => b.bucket);
  const counts = scoreDistribution.map(b => b.count);
  const interviewCounts = scoreDistribution.map(b => b.interview_count);

  chartInstances.score = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: t('analytics.applications_label'),
          data: counts,
          backgroundColor: 'rgba(77,166,255,.6)',
          borderRadius: 4,
        },
        {
          label: t('analytics.funnel_interview'),
          data: interviewCounts,
          backgroundColor: 'rgba(83,215,105,.6)',
          borderRadius: 4,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { color: '#8892a4', padding: 12 } },
        tooltip: {
          callbacks: {
            afterBody: (items) => {
              const idx = items[0].dataIndex;
              const b = scoreDistribution[idx];
              if (b.count > 0) {
                return t('analytics.score_tooltip_interviews', { count: b.interview_count, rate: b.interview_rate });
              }
              return '';
            }
          }
        }
      },
      scales: {
        x: { ticks: { color: '#8892a4' }, grid: { display: false } },
        y: { ticks: { color: '#8892a4', stepSize: 1 }, grid: { color: 'rgba(255,255,255,.05)' }, beginAtZero: true },
      },
    },
  });
}

/* ── Weekly Summary (FR-096) ─────────────────────────────────── */

function renderWeeklySummary(weekly) {
  const container = document.getElementById('weekly-summary-container');
  if (!container) return;

  const cur = weekly.current;
  const prev = weekly.previous;
  const chg = weekly.changes;

  const row = (label, curVal, prevVal, change, isScore) => {
    const curStr = curVal != null ? curVal : '—';
    const prevStr = prevVal != null ? prevVal : '—';
    let changeStr = '—';
    let cls = 'trend-neutral';
    if (change != null && change !== 0) {
      if (!isScore && prevVal === 0) {
        changeStr = (change > 0 ? '+' : '') + change;
      } else if (prevVal != null && prevVal !== 0) {
        const pct = ((change / Math.abs(prevVal)) * 100).toFixed(1);
        changeStr = (change > 0 ? '+' : '') + pct + '%';
      } else {
        changeStr = (change > 0 ? '+' : '') + (isScore ? change.toFixed(1) : change);
      }
      cls = change > 0 ? 'trend-up' : 'trend-down';
    }
    return `<div class="weekly-header">${escHtml(label)}</div>
      <div class="weekly-val">${curStr}</div>
      <div class="weekly-val">${prevStr}</div>
      <div class="weekly-val ${cls}">${changeStr}</div>`;
  };

  container.innerHTML = `<div class="weekly-grid">
    <div class="weekly-header"></div>
    <div class="weekly-header" style="text-align:center">${escHtml(t('analytics.weekly_current'))}</div>
    <div class="weekly-header" style="text-align:center">${escHtml(t('analytics.weekly_previous'))}</div>
    <div class="weekly-header" style="text-align:center">${escHtml(t('analytics.weekly_change'))}</div>
    ${row(t('analytics.weekly_applications'), cur.applications, prev.applications, chg.applications, false)}
    ${row(t('analytics.weekly_interviews'), cur.interviews, prev.interviews, chg.interviews, false)}
    ${row(t('analytics.weekly_avg_score'), cur.avg_score, prev.avg_score, chg.avg_score, true)}
  </div>`;
}

/* ── Top Companies Table (FR-097) ────────────────────────────── */

function renderTopCompanies(topCompanies) {
  const container = document.getElementById('top-companies-container');
  if (!container) return;

  if (!topCompanies || topCompanies.length === 0) {
    container.innerHTML = `<div class="analytics-empty">${escHtml(t('analytics.empty_state'))}</div>`;
    return;
  }

  const hName = escHtml(t('analytics.companies_col_name'));
  const hTotal = escHtml(t('analytics.companies_col_total'));
  const hStatuses = escHtml(t('analytics.companies_col_statuses'));

  let html = `<table class="analytics-table" role="table">
    <thead><tr>
      <th scope="col">${hName}</th><th scope="col">${hTotal}</th>
      <th scope="col">${hStatuses}</th>
    </tr></thead><tbody>`;

  for (const c of topCompanies) {
    const badges = Object.entries(c.statuses)
      .map(([s, count]) => `<span class="status-mini-badge" style="background:${_statusColor(s)}">${escHtml(s)} ${count}</span>`)
      .join('');
    html += `<tr><td>${escHtml(c.company)}</td><td>${c.total}</td><td>${badges}</td></tr>`;
  }
  html += '</tbody></table>';
  container.innerHTML = html;
}

/* ── Response Times (FR-098) ─────────────────────────────────── */

function renderResponseTimes(responseTimes) {
  const container = document.getElementById('response-times-container');
  if (!container) return;

  const section = (label, data) => {
    const median = data.median_days != null ? t('analytics.response_days', { days: data.median_days }) : '—';
    const avg = data.avg_days != null ? t('analytics.response_days', { days: data.avg_days }) : '—';
    return `<div class="response-metric-group">
      <h4>${escHtml(label)}</h4>
      <div class="response-metric-row">
        <span class="metric-label">${escHtml(t('analytics.response_median'))}</span>
        <span class="metric-value">${escHtml(median)}</span>
      </div>
      <div class="response-metric-row">
        <span class="metric-label">${escHtml(t('analytics.response_average'))}</span>
        <span class="metric-value">${escHtml(avg)}</span>
      </div>
    </div>`;
  };

  container.innerHTML = `<div class="response-metrics">
    ${section(t('analytics.response_to_interview'), responseTimes.to_interview)}
    ${section(t('analytics.response_to_rejected'), responseTimes.to_rejected)}
  </div>`;
}

/* ── Helpers ──────────────────────────────────────────────────── */

function _capitalize(s) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : '';
}

function _statusColor(status) {
  if (status === 'applied') return 'rgba(77,166,255,.3)';
  if (status === 'interview' || status === 'interviewing' || status === 'interviewed') return 'rgba(83,215,105,.3)';
  if (status === 'offer' || status === 'accepted') return 'rgba(255,193,7,.3)';
  if (status === 'rejected') return 'rgba(233,69,96,.3)';
  if (status === 'error') return 'rgba(255,107,107,.3)';
  return 'rgba(136,146,164,.3)';
}

function _showEmpty(parentNode) {
  const existing = parentNode.querySelector('.analytics-empty');
  if (!existing) {
    const div = document.createElement('div');
    div.className = 'analytics-empty';
    div.textContent = t('analytics.empty_state');
    parentNode.appendChild(div);
  }
}
