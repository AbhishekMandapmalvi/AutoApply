/* ═══════════════════════════════════════════════════════════════
   LIVE FEED
   ═══════════════════════════════════════════════════════════════ */
import { escHtml } from './helpers.js';
import { t } from './i18n.js';

let feedStarted = false;
let feedHistoryLoaded = false;

export async function loadFeedHistory() {
  if (feedHistoryLoaded) return;
  try {
    const res = await fetch('/api/feed?limit=50');
    if (!res.ok) return;
    const events = await res.json();
    if (!events.length) return;
    // Events come newest-first from API; reverse so oldest is added first
    const reversed = events.reverse();
    for (const evt of reversed) {
      addFeedItem({
        type: evt.event_type,
        job_title: evt.job_title,
        company: evt.company,
        platform: evt.platform,
        message: evt.message,
        timestamp: evt.created_at,
      });
    }
    feedHistoryLoaded = true;
  } catch (e) {
    console.warn('[feed] Could not load history:', e);
  }
}

export function addFeedItem(evt) {
  const list = document.getElementById('feed-list');
  // Remove empty placeholder on first item
  const empty = document.getElementById('feed-empty');
  if (empty) empty.remove();

  const item = document.createElement('div');
  item.className = 'feed-item';

  const time = evt.timestamp
    ? new Date(evt.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const type = evt.type || 'INFO';

  // Backend sends job_title/company/platform/message
  const title = evt.job_title || evt.title || '';
  const company = evt.company || '';
  const platform = evt.platform || '';
  const message = evt.message || '';

  // Build the detail line: show job info if available, otherwise show message
  let detailHtml = '';
  if (title) {
    detailHtml = `<strong>${escHtml(title)}</strong>`;
    if (company) detailHtml += ` ${t('review.at')} <strong>${escHtml(company)}</strong>`;
    if (platform) detailHtml += ` <span class="text-dim">(${escHtml(platform)})</span>`;
    // Show message as a secondary line if it adds info beyond the title
    if (message && !message.includes(title)) {
      detailHtml += `<span class="feed-msg">${escHtml(message)}</span>`;
    }
  } else if (message) {
    detailHtml = `${escHtml(message)}`;
  }

  item.innerHTML = `
    <span class="feed-time">${time}</span>
    <span class="feed-badge ${escHtml(type)}">${escHtml(type)}</span>
    <span class="feed-detail">${detailHtml}</span>
  `;

  list.prepend(item);

  // Keep max 200 items
  while (list.children.length > 200) list.removeChild(list.lastChild);

  // Update counter
  updateFeedCount();
}

export function clearFeed() {
  const list = document.getElementById('feed-list');
  list.innerHTML = `<div class="text-center text-dim" id="feed-empty" style="padding:40px 0;">${t('feed.empty')}</div>`;
  feedStarted = false;
  feedHistoryLoaded = false;
  updateFeedCount();
}

function updateFeedCount() {
  const list = document.getElementById('feed-list');
  const count = list.querySelectorAll('.feed-item').length;
  const el = document.getElementById('feed-count');
  if (el) el.textContent = count > 0 ? `(${count})` : '';
}
