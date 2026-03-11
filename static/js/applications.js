/* ═══════════════════════════════════════════════════════════════
   APPLICATIONS
   ═══════════════════════════════════════════════════════════════ */
import { state } from './state.js';
import { escHtml, escAttr, matchColor, badgeClass } from './helpers.js';
import { closeModal, openModal } from './modals.js';
import { t } from './i18n.js';

let searchTimeout = null;

export function debounceSearch() {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(loadApplications, 350);
}

export async function loadApplications() {
  const status   = document.getElementById('filter-status').value;
  const platform = document.getElementById('filter-platform').value;
  const search   = document.getElementById('filter-search').value;
  const params = new URLSearchParams({
    page: state.appPage,
    per_page: state.appPageSize,
    ...(status && { status }),
    ...(platform && { platform }),
    ...(search && { search }),
  });

  const body = document.getElementById('applications-body');
  try {
    const res = await fetch('/api/applications?' + params);
    const data = await res.json();
    const apps = data.applications || [];
    const total = data.total || 0;

    if (!apps.length) {
      body.innerHTML = `<tr><td colspan="9" class="text-center text-dim" style="padding:40px 0;">${t('applications.no_results')}</td></tr>`;
      document.getElementById('applications-pagination').innerHTML = '';
      return;
    }

    body.innerHTML = apps.map(a => `
      <tr class="clickable-row" data-app-id="${a.id}" tabindex="0" role="row" aria-label="${escAttr((a.job_title || a.title || '') + ' ' + t('review.at') + ' ' + (a.company || ''))}">
        <td>${escHtml(a.company || '')}</td>
        <td><strong>${escHtml(a.job_title || a.title || '')}</strong></td>
        <td>${escHtml(a.platform || '')}</td>
        <td><span class="match-pct" style="color:${matchColor(a.match_score)}">${a.match_score != null ? a.match_score + '%' : '--'}</span></td>
        <td class="no-row-click">
          <select data-status-id="${a.id}" aria-label="Status for ${escAttr(a.job_title || '')}">
            ${['applied','interview','rejected','offer','withdrawn','error','manual_required'].map(s =>
              `<option value="${s}" ${a.status === s ? 'selected' : ''}>${t('status.' + s)}</option>`
            ).join('')}
          </select>
        </td>
        <td class="text-dim" style="white-space:nowrap;">${(a.applied_at || a.applied_date) ? new Date(a.applied_at || a.applied_date).toLocaleDateString() : '--'}</td>
        <td class="no-row-click">${a.resume_path ? `<a href="/api/applications/${a.id}/resume" target="_blank" style="font-size:.82rem;" aria-label="Download resume for ${escAttr(a.job_title || '')}">${t('button.download')}</a>` : '--'}</td>
        <td class="no-row-click">${(a.cover_letter_text || a.cover_letter) ? `<button class="btn btn-ghost btn-sm" data-cover-id="${a.id}" aria-label="View cover letter for ${escAttr(a.job_title || '')}">${t('button.view')}</button>` : '--'}</td>
        <td class="no-row-click"><input class="notes-input" value="${escAttr(a.notes || '')}" data-notes-id="${a.id}" placeholder="${t('placeholder.notes')}" aria-label="Notes for ${escAttr(a.job_title || '')}"></td>
      </tr>
    `).join('');

    // Pagination
    const pages = Math.ceil(total / state.appPageSize);
    renderPagination(pages);
  } catch (e) {
    body.innerHTML = `<tr><td colspan="9" class="text-center text-dim" style="padding:40px 0;">${t('applications.load_error')}</td></tr>`;
  }
}

function renderPagination(totalPages) {
  const wrap = document.getElementById('applications-pagination');
  if (totalPages <= 1) { wrap.innerHTML = ''; return; }
  let html = `<button ${state.appPage <= 1 ? 'disabled' : ''} data-page="${state.appPage - 1}" aria-label="${t('applications.previous_page')}">&laquo;</button>`;
  const start = Math.max(1, state.appPage - 2);
  const end = Math.min(totalPages, start + 4);
  for (let i = start; i <= end; i++) {
    html += `<button class="${i === state.appPage ? 'active' : ''}" data-page="${i}" aria-label="Page ${i}"${i === state.appPage ? ' aria-current="page"' : ''}>${i}</button>`;
  }
  html += `<button ${state.appPage >= totalPages ? 'disabled' : ''} data-page="${state.appPage + 1}" aria-label="${t('applications.next_page')}">&raquo;</button>`;
  wrap.innerHTML = html;
}

export function goAppPage(p) {
  state.appPage = p;
  loadApplications();
}

export async function updateAppStatus(id, status) {
  try { await fetch(`/api/applications/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status }) }); } catch { }
}

export async function updateAppNotes(id, notes) {
  try { await fetch(`/api/applications/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ notes }) }); loadApplications(); } catch { }
}

export async function viewCoverLetter(id) {
  try {
    const res = await fetch(`/api/applications/${id}/cover_letter`);
    const data = await res.json();
    document.getElementById('modal-cover-letter-content').textContent = data.cover_letter_text || t('applications.no_cover_letter');
    openModal('modal-cover-letter');
  } catch { }
}

export async function viewApplicationDetail(id) {
  const content = document.getElementById('app-detail-content');
  content.innerHTML = `<div class="text-center text-dim" style="padding:30px;">${t('applications.loading')}</div>`;
  openModal('modal-app-detail');
  try {
    const [appRes, eventsRes] = await Promise.all([
      fetch(`/api/applications/${id}`),
      fetch(`/api/applications/${id}/events`),
    ]);
    const app = await appRes.json();
    const events = await eventsRes.json();
    if (app.error) { content.innerHTML = `<div class="text-dim">${escHtml(app.error)}</div>`; return; }

    const statusOptions = ['applied','interview','rejected','offer','withdrawn','error','manual_required'];
    const fmtDate = d => d ? new Date(d).toLocaleString() : '--';

    let timeline = '';
    if (Array.isArray(events) && events.length) {
      timeline = `<ul class="app-timeline">${events.map(e => `
        <li>
          <span class="badge badge-${badgeClass(e.event_type)}" style="font-size:.75rem;">${escHtml(e.event_type)}</span>
          ${escHtml(e.message || '')}
          <div class="timeline-time">${fmtDate(e.created_at)}</div>
        </li>`).join('')}</ul>`;
    } else {
      timeline = `<div class="text-dim" style="font-size:.88rem;">${t('applications.no_activity')}</div>`;
    }

    content.innerHTML = `
      <div class="app-detail-header">
        <h3>${escHtml(app.job_title || '')}</h3>
        <div class="company-line">${escHtml(app.company || '')}${app.location ? ' &mdash; ' + escHtml(app.location) : ''}</div>
      </div>
      <div class="app-detail-grid">
        <div><div class="detail-label">${t('applications.label_platform')}</div><div class="detail-value">${escHtml(app.platform || '')}</div></div>
        <div><div class="detail-label">${t('applications.label_match_score')}</div><div class="detail-value"><span style="color:${matchColor(app.match_score)}">${app.match_score != null ? app.match_score + '%' : '--'}</span></div></div>
        <div><div class="detail-label">${t('applications.label_applied')}</div><div class="detail-value">${fmtDate(app.applied_at)}</div></div>
        <div><div class="detail-label">${t('applications.label_updated')}</div><div class="detail-value">${fmtDate(app.updated_at)}</div></div>
        <div><div class="detail-label">${t('applications.label_salary')}</div><div class="detail-value">${escHtml(app.salary || t('applications.not_specified'))}</div></div>
        <div><div class="detail-label">${t('applications.label_status')}</div><div class="detail-value">
          <select id="detail-status-select" data-detail-status-id="${app.id}" style="font-size:.9rem;" aria-label="${t('applications.label_status')}">
            ${statusOptions.map(s => `<option value="${s}" ${app.status === s ? 'selected' : ''}>${t('status.' + s)}</option>`).join('')}
          </select>
        </div></div>
      </div>
      ${app.error_message ? `<div class="app-detail-section"><h4>${t('applications.label_error')}</h4><div style="color:var(--danger);font-size:.9rem;">${escHtml(app.error_message)}</div></div>` : ''}
      <div class="app-detail-section">
        <h4>${t('applications.label_notes')}</h4>
        <textarea class="app-detail-notes" id="detail-notes-input" placeholder="${t('applications.notes_placeholder')}">${escHtml(app.notes || '')}</textarea>
        <button class="btn btn-sm" style="margin-top:6px;" data-save-notes-id="${app.id}">${t('button.save_notes')}</button>
      </div>
      <div class="app-detail-section">
        <h4>${t('applications.label_timeline')}</h4>
        ${timeline}
      </div>
      <div class="app-detail-actions">
        ${app.apply_url ? `<a href="${escAttr(app.apply_url)}" target="_blank" rel="noopener" class="btn btn-ghost btn-sm">${t('applications.view_job_posting')}</a>` : ''}
        ${app.description_path ? `<a href="/api/applications/${app.id}/description" target="_blank" class="btn btn-ghost btn-sm">${t('applications.view_description')}</a>` : ''}
        ${app.resume_path ? `<a href="/api/applications/${app.id}/resume" target="_blank" class="btn btn-ghost btn-sm">${t('applications.download_resume')}</a>` : ''}
        ${app.cover_letter_text ? `<button class="btn btn-ghost btn-sm" data-detail-cover-id="${app.id}">${t('applications.view_cover_letter')}</button>` : ''}
      </div>
    `;
  } catch (e) {
    content.innerHTML = `<div class="text-dim">${t('applications.detail_load_error')}</div>`;
  }
}

export async function updateDetailStatus(id) {
  const status = document.getElementById('detail-status-select').value;
  try { await fetch(`/api/applications/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status }) }); } catch { }
}

export async function saveDetailNotes(id) {
  const notes = document.getElementById('detail-notes-input').value;
  try { await fetch(`/api/applications/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ notes }) }); } catch { }
}

export function exportCSV() {
  const status   = document.getElementById('filter-status').value;
  const platform = document.getElementById('filter-platform').value;
  const search   = document.getElementById('filter-search').value;
  const params = new URLSearchParams({
    format: 'csv',
    ...(status && { status }),
    ...(platform && { platform }),
    ...(search && { search }),
  });
  window.open('/api/applications/export?' + params, '_blank');
}
