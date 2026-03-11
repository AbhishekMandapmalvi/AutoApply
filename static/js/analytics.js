/* ═══════════════════════════════════════════════════════════════
   ANALYTICS CHARTS
   ═══════════════════════════════════════════════════════════════ */
import { t } from './i18n.js';

let chartInstances = {};

export async function loadAnalytics() {
  try {
    const [summaryRes, dailyRes] = await Promise.all([
      fetch('/api/analytics/summary'),
      fetch('/api/analytics/daily?days=30'),
    ]);
    const summary = await summaryRes.json();
    const daily = await dailyRes.json();

    renderDailyChart(daily);
    renderStatusChart(summary.by_status || {});
    renderPlatformChart(summary.by_platform || {});
  } catch (e) {
    console.warn('Could not load analytics:', e);
  }
}

function renderDailyChart(data) {
  const ctx = document.getElementById('chart-daily');
  if (!ctx) return;
  if (chartInstances.daily) chartInstances.daily.destroy();
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

function renderStatusChart(byStatus) {
  const ctx = document.getElementById('chart-status');
  if (!ctx) return;
  if (chartInstances.status) chartInstances.status.destroy();
  const labels = Object.keys(byStatus);
  const values = Object.values(byStatus);
  const colors = labels.map(s => {
    if (s === 'applied') return '#4da6ff';
    if (s === 'interview') return '#53d769';
    if (s === 'offer') return '#ffc107';
    if (s === 'rejected') return '#e94560';
    if (s === 'error') return '#ff6b6b';
    return '#8892a4';
  });
  chartInstances.status = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: labels.map(s => { const tr = t('status.' + s); return tr !== 'status.' + s ? tr : s.charAt(0).toUpperCase() + s.slice(1); }),
      datasets: [{ data: values, backgroundColor: colors, borderWidth: 0 }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { color: '#8892a4', padding: 12 } },
      },
    },
  });
}

function renderPlatformChart(byPlatform) {
  const ctx = document.getElementById('chart-platform');
  if (!ctx) return;
  if (chartInstances.platform) chartInstances.platform.destroy();
  chartInstances.platform = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: Object.keys(byPlatform).map(s => s.charAt(0).toUpperCase() + s.slice(1)),
      datasets: [{
        label: t('analytics.applications_label'),
        data: Object.values(byPlatform),
        backgroundColor: '#4da6ff',
        borderRadius: 6,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#8892a4' }, grid: { display: false } },
        y: { ticks: { color: '#8892a4', stepSize: 1 }, grid: { color: 'rgba(255,255,255,.05)' }, beginAtZero: true },
      },
    },
  });
}
