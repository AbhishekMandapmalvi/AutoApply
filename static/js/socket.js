/* ═══════════════════════════════════════════════════════════════
   SOCKET.IO
   ═══════════════════════════════════════════════════════════════ */
import { state } from './state.js';
import { updateBotUI, renderStats } from './bot-control.js';
import { addFeedItem } from './feed.js';
import { showReviewCard, hideReviewCard } from './review.js';
import { showLoginGateModal, hideLoginGateModal } from './login-gate.js';
import { updateAIIndicators } from './ai-status.js';

export function initSocket() {
  let socket;
  try {
    socket = io();
    socket.on('connect', () => console.log('[socket] connected'));
    socket.on('bot_status', handleBotStatus);
    socket.on('feed_event', handleFeedEvent);
  } catch (e) {
    console.warn('[socket] Could not connect:', e);
  }
}

function handleBotStatus(data) {
  if (data.status) updateBotUI(data.status);
  // Sync stats from server (backend sends flat fields)
  if (typeof data.jobs_found_today === 'number') state.stats.found = data.jobs_found_today;
  if (typeof data.applied_today === 'number')    state.stats.applied = data.applied_today;
  if (typeof data.errors_today === 'number')     state.stats.errors = data.errors_today;
  renderStats();
  if (typeof data.ai_available === 'boolean') {
    state.aiAvailable = data.ai_available;
    updateAIIndicators();
    const banner = document.getElementById('ai-warning-banner');
    if (banner) banner.classList.toggle('hidden', state.aiAvailable);
  }
  // Hide review card if bot is no longer awaiting review
  if (data.awaiting_review === false) {
    hideReviewCard();
  }
  // Show/hide login gate modal (FR-089)
  if (data.awaiting_login === true && data.login_context) {
    showLoginGateModal(data.login_context);
  } else if (data.awaiting_login === false) {
    hideLoginGateModal();
  }
}

function handleFeedEvent(evt) {
  addFeedItem(evt);
  // Update quick stats
  if (evt.type === 'FOUND')   state.stats.found++;
  if (evt.type === 'APPLIED') state.stats.applied++;
  if (evt.type === 'ERROR' || evt.type === 'CAPTCHA') state.stats.errors++;
  renderStats();

  // Show review card when REVIEW event arrives
  if (evt.type === 'REVIEW') {
    showReviewCard(evt);
  }
  // Show login gate modal when LOGIN_REQUIRED event arrives (FR-089)
  if (evt.type === 'LOGIN_REQUIRED') {
    showLoginGateModal({ domain: evt.domain, portal_type: evt.portal_type, url: evt.apply_url });
  }
  // Hide review card on APPLIED, SKIPPED, or ERROR for the same job
  if (['APPLIED', 'SKIPPED', 'ERROR'].includes(evt.type)) {
    hideReviewCard();
    hideLoginGateModal();
  }
}
