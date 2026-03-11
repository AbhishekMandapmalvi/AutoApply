/* ═══════════════════════════════════════════════════════════════
   BOT CONTROL
   ═══════════════════════════════════════════════════════════════ */
import { state } from './state.js';
import { t } from './i18n.js';

export async function botControl(action) {
  try {
    await fetch(`/api/bot/${action}`, { method: 'POST' });
    updateBotUI(action === 'start' ? 'running' : action === 'pause' ? 'paused' : 'stopped');
  } catch (e) {
    console.warn('Bot control error:', e);
  }
}

export function updateBotUI(status) {
  state.botStatus = status;
  const dot = document.getElementById('bot-dot');
  const label = document.getElementById('bot-status-label');
  const btnStart = document.getElementById('btn-start');
  const btnPause = document.getElementById('btn-pause');
  const btnStop  = document.getElementById('btn-stop');

  dot.className = 'dot dot-pulse';
  if (status === 'running') {
    dot.classList.add('dot-green');
    label.textContent = t('bot.running');
    btnStart.disabled = true;
    btnPause.disabled = false;
    btnStop.disabled  = false;
    if (!state.botStartTime) state.botStartTime = Date.now();
    startUptimeTimer();
  } else if (status === 'paused') {
    dot.classList.add('dot-yellow');
    label.textContent = t('bot.paused');
    btnStart.disabled = false;
    btnPause.disabled = true;
    btnStop.disabled  = false;
    stopUptimeTimer();
  } else {
    dot.classList.add('dot-red');
    dot.classList.remove('dot-pulse');
    label.textContent = t('bot.stopped');
    btnStart.disabled = false;
    btnPause.disabled = true;
    btnStop.disabled  = true;
    state.botStartTime = null;
    stopUptimeTimer();
    document.getElementById('stat-uptime').textContent = t('bot.uptime_default');
  }
}

export function renderStats() {
  document.getElementById('stat-found').textContent   = state.stats.found;
  document.getElementById('stat-applied').textContent  = state.stats.applied;
  document.getElementById('stat-errors').textContent   = state.stats.errors;
}

function startUptimeTimer() {
  stopUptimeTimer();
  state.uptimeInterval = setInterval(() => {
    if (!state.botStartTime) return;
    const s = Math.floor((Date.now() - state.botStartTime) / 1000);
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    document.getElementById('stat-uptime').textContent =
      (h ? h + ':' : '') + String(m).padStart(2, '0') + ':' + String(sec).padStart(2, '0');
  }, 1000);
}

function stopUptimeTimer() {
  if (state.uptimeInterval) { clearInterval(state.uptimeInterval); state.uptimeInterval = null; }
}
