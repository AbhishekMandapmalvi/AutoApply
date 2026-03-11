/* ═══════════════════════════════════════════════════════════════
   KNOWLEDGE BASE — Upload, view, edit, delete KB entries
   ═══════════════════════════════════════════════════════════════ */

import { t, _applyDataI18n } from './i18n.js';
import { escHtml, escAttr } from './helpers.js';

let kbPage = 0;
let kbLimit = 50;
let kbCategory = '';
let kbSearch = '';

// ---------------------------------------------------------------------------
// Load & render
// ---------------------------------------------------------------------------

export async function loadKnowledgeBase() {
  await Promise.all([loadKBStats(), loadKBEntries()]);
}

async function loadKBStats() {
  try {
    const res = await fetch('/api/kb/stats');
    if (!res.ok) return;
    const stats = await res.json();
    const el = document.getElementById('kb-stats');
    if (!el) return;

    const cats = stats.by_category || {};
    const total = stats.total || Object.values(cats).reduce((a, b) => a + b, 0);
    let html = `<div class="kb-stat-card"><strong>${escHtml(t('kb.stats_total'))}</strong><span class="kb-stat-value">${total}</span></div>`;
    for (const [cat, count] of Object.entries(cats)) {
      const label = t(`kb.category_${cat}`) || cat;
      html += `<div class="kb-stat-card"><strong>${escHtml(label)}</strong><span class="kb-stat-value">${count}</span></div>`;
    }
    el.innerHTML = html;
  } catch (e) {
    console.warn('Failed to load KB stats:', e);
  }
}

export async function loadKBEntries() {
  const listEl = document.getElementById('kb-entries-list');
  if (!listEl) return;

  const params = new URLSearchParams({
    limit: kbLimit,
    offset: kbPage * kbLimit,
  });
  if (kbCategory) params.set('category', kbCategory);
  if (kbSearch) params.set('search', kbSearch);

  try {
    const res = await fetch(`/api/kb?${params}`);
    if (!res.ok) { listEl.innerHTML = `<p>${escHtml(t('kb.entries_empty'))}</p>`; return; }
    const data = await res.json();
    const entries = data.entries || [];

    if (!entries.length) {
      listEl.innerHTML = `<p class="text-muted" data-i18n="kb.entries_empty">${escHtml(t('kb.entries_empty'))}</p>`;
      _applyDataI18n(listEl);
      renderKBPagination(0);
      return;
    }

    let html = `<table class="data-table kb-table" role="table" aria-label="${escAttr(t('kb.entries_title'))}">
      <thead><tr>
        <th data-i18n="kb.col_category">${escHtml(t('kb.col_category'))}</th>
        <th data-i18n="kb.col_subsection">${escHtml(t('kb.col_subsection'))}</th>
        <th data-i18n="kb.col_text">${escHtml(t('kb.col_text'))}</th>
        <th data-i18n="kb.col_tags">${escHtml(t('kb.col_tags'))}</th>
        <th data-i18n="kb.col_actions">${escHtml(t('kb.col_actions'))}</th>
      </tr></thead><tbody>`;

    for (const e of entries) {
      const catLabel = t(`kb.category_${e.category}`) || e.category || '';
      const text = (e.text || '').length > 120 ? e.text.slice(0, 120) + '…' : (e.text || '');
      const tags = e.tags ? (typeof e.tags === 'string' ? e.tags : JSON.stringify(e.tags)) : '';
      html += `<tr>
        <td><span class="badge badge-${escAttr(e.category || 'info')}">${escHtml(catLabel)}</span></td>
        <td>${escHtml(e.subsection || '')}</td>
        <td class="kb-text-cell" title="${escAttr(e.text || '')}">${escHtml(text)}</td>
        <td>${escHtml(tags)}</td>
        <td class="kb-actions no-row-click">
          <button type="button" class="btn btn-sm btn-secondary" data-kb-edit="${e.id}"
                  aria-label="${escAttr(t('kb.edit_entry'))}"
                  data-i18n="kb.edit_entry">Edit</button>
          <button type="button" class="btn btn-sm btn-danger" data-kb-delete="${e.id}"
                  aria-label="${escAttr(t('kb.delete_entry'))}"
                  data-i18n="kb.delete_entry">Delete</button>
        </td>
      </tr>`;
    }
    html += '</tbody></table>';
    listEl.innerHTML = html;
    _applyDataI18n(listEl);
    renderKBPagination(data.count || entries.length);
  } catch (e) {
    console.warn('Failed to load KB entries:', e);
    listEl.innerHTML = `<p class="text-muted">${escHtml(t('kb.entries_empty'))}</p>`;
  }
}

function renderKBPagination(totalCount) {
  const el = document.getElementById('kb-pagination');
  if (!el) return;
  const totalPages = Math.max(1, Math.ceil(totalCount / kbLimit));
  const currentPage = kbPage + 1;

  if (totalPages <= 1) { el.innerHTML = ''; return; }
  el.innerHTML = `
    <button type="button" class="btn btn-sm btn-secondary" ${currentPage <= 1 ? 'disabled' : ''}
            onclick="switchKBPage(${kbPage - 1})">&laquo;</button>
    <span>${currentPage} / ${totalPages}</span>
    <button type="button" class="btn btn-sm btn-secondary" ${currentPage >= totalPages ? 'disabled' : ''}
            onclick="switchKBPage(${kbPage + 1})">&raquo;</button>
  `;
}

export function switchKBPage(page) {
  if (page < 0) return;
  kbPage = page;
  loadKBEntries();
}

// ---------------------------------------------------------------------------
// Filter & search
// ---------------------------------------------------------------------------

export function filterKBCategory(cat) {
  kbCategory = cat === 'all' ? '' : cat;
  kbPage = 0;
  loadKBEntries();
}

let _searchTimer;
export function searchKB(query) {
  clearTimeout(_searchTimer);
  _searchTimer = setTimeout(() => {
    kbSearch = query;
    kbPage = 0;
    loadKBEntries();
  }, 300);
}

// ---------------------------------------------------------------------------
// Upload
// ---------------------------------------------------------------------------

export async function uploadKBDocument() {
  const input = document.getElementById('kb-upload-input');
  if (!input || !input.files.length) return;

  const file = input.files[0];
  const statusEl = document.getElementById('kb-upload-status');
  if (statusEl) {
    statusEl.textContent = t('kb.upload_processing');
    statusEl.className = 'kb-upload-status text-info';
  }

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch('/api/kb/upload', { method: 'POST', body: formData });
    const data = await res.json();

    if (res.ok) {
      if (statusEl) {
        statusEl.textContent = t('kb.upload_success').replace('{count}', data.entries_created || 0);
        statusEl.className = 'kb-upload-status text-success';
      }
      input.value = '';
      loadKnowledgeBase();
    } else {
      const msg = data.description || data.message || 'Upload failed';
      if (statusEl) {
        statusEl.textContent = t('kb.upload_error').replace('{error}', msg);
        statusEl.className = 'kb-upload-status text-danger';
      }
    }
  } catch (e) {
    if (statusEl) {
      statusEl.textContent = t('kb.upload_error').replace('{error}', e.message);
      statusEl.className = 'kb-upload-status text-danger';
    }
  }
}

// ---------------------------------------------------------------------------
// Edit entry
// ---------------------------------------------------------------------------

export async function editKBEntry(id) {
  try {
    const res = await fetch(`/api/kb/${id}`);
    if (!res.ok) return;
    const entry = await res.json();

    const overlay = document.getElementById('kb-edit-overlay');
    if (!overlay) return;

    const content = overlay.querySelector('.kb-edit-content') || overlay;
    content.innerHTML = `
      <h3 data-i18n="kb.edit_entry">${escHtml(t('kb.edit_entry'))}</h3>
      <div class="flex-col gap-md">
        <label>${escHtml(t('kb.col_category'))}
          <select id="kb-edit-category" class="form-input" aria-label="${escAttr(t('kb.col_category'))}">
            ${['experience','skill','education','project','certification','summary','award','volunteer']
              .map(c => `<option value="${c}" ${c === entry.category ? 'selected' : ''}>${escHtml(t('kb.category_' + c) || c)}</option>`)
              .join('')}
          </select>
        </label>
        <label>${escHtml(t('kb.col_subsection'))}
          <input id="kb-edit-subsection" class="form-input" value="${escAttr(entry.subsection || '')}"
                 aria-label="${escAttr(t('kb.col_subsection'))}">
        </label>
        <label>${escHtml(t('kb.col_text'))}
          <textarea id="kb-edit-text" class="form-input" rows="5"
                    aria-label="${escAttr(t('kb.col_text'))}">${escHtml(entry.text || '')}</textarea>
        </label>
        <label>${escHtml(t('kb.col_tags'))}
          <input id="kb-edit-tags" class="form-input" value="${escAttr(entry.tags || '')}"
                 aria-label="${escAttr(t('kb.col_tags'))}">
        </label>
        <div class="flex-row gap-md">
          <button type="button" class="btn btn-primary" onclick="saveKBEntry(${id})">Save</button>
          <button type="button" class="btn btn-secondary" onclick="closeKBEdit()">Cancel</button>
        </div>
      </div>
    `;
    _applyDataI18n(content);
    overlay.classList.remove('hidden');
    overlay.querySelector('textarea')?.focus();
  } catch (e) {
    console.warn('Failed to load KB entry:', e);
  }
}

export async function saveKBEntry(id) {
  const text = document.getElementById('kb-edit-text')?.value;
  const subsection = document.getElementById('kb-edit-subsection')?.value;
  const tags = document.getElementById('kb-edit-tags')?.value;

  try {
    const res = await fetch(`/api/kb/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, subsection, tags }),
    });
    if (res.ok) {
      closeKBEdit();
      loadKBEntries();
    }
  } catch (e) {
    console.warn('Failed to save KB entry:', e);
  }
}

export function closeKBEdit() {
  const overlay = document.getElementById('kb-edit-overlay');
  if (overlay) overlay.classList.add('hidden');
}

// ---------------------------------------------------------------------------
// Delete entry
// ---------------------------------------------------------------------------

export async function deleteKBEntry(id) {
  if (!confirm(t('kb.delete_confirm'))) return;

  try {
    const res = await fetch(`/api/kb/${id}`, { method: 'DELETE' });
    if (res.ok) loadKBEntries();
  } catch (e) {
    console.warn('Failed to delete KB entry:', e);
  }
}

// ---------------------------------------------------------------------------
// Documents list
// ---------------------------------------------------------------------------

export async function loadKBDocuments() {
  const el = document.getElementById('kb-documents-list');
  if (!el) return;

  try {
    const res = await fetch('/api/kb/documents');
    if (!res.ok) return;
    const data = await res.json();
    const docs = data.documents || [];

    if (!docs.length) {
      el.innerHTML = '<p class="text-muted">No documents uploaded yet.</p>';
      return;
    }

    let html = '<ul class="kb-documents">';
    for (const d of docs) {
      html += `<li>
        <strong>${escHtml(d.filename || d.original_filename || 'Document')}</strong>
        <span class="text-muted">${escHtml(d.uploaded_at || '')}</span>
        <span class="badge">${d.entries_extracted || 0} entries</span>
      </li>`;
    }
    html += '</ul>';
    el.innerHTML = html;
  } catch (e) {
    console.warn('Failed to load KB documents:', e);
  }
}

// ---------------------------------------------------------------------------
// ATS Scoring
// ---------------------------------------------------------------------------

export async function analyzeATS() {
  const jdEl = document.getElementById('kb-ats-jd');
  const platformEl = document.getElementById('kb-ats-platform');
  const resultEl = document.getElementById('kb-ats-result');
  const statusEl = document.getElementById('kb-ats-status');

  const jdText = jdEl?.value?.trim();
  if (!jdText) {
    if (statusEl) { statusEl.textContent = t('errors.invalid_request'); statusEl.className = 'text-danger'; }
    return;
  }

  if (statusEl) { statusEl.textContent = t('ats.analyzing'); statusEl.className = 'text-info'; }

  try {
    const res = await fetch('/api/kb/ats-score', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        jd_text: jdText,
        platform: platformEl?.value || 'default',
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      if (statusEl) { statusEl.textContent = err.description || 'Scoring failed'; statusEl.className = 'text-danger'; }
      return;
    }

    const data = await res.json();
    if (statusEl) { statusEl.textContent = ''; statusEl.className = ''; }
    renderATSResult(data, resultEl);
  } catch (e) {
    if (statusEl) { statusEl.textContent = e.message; statusEl.className = 'text-danger'; }
  }
}

function renderATSResult(data, el) {
  if (!el) return;

  const scoreColor = data.score >= 80 ? 'var(--success)' : data.score >= 60 ? 'var(--warning)' : 'var(--danger)';

  let html = `<div class="ats-result">
    <div class="ats-score-badge" style="border-color:${scoreColor}; color:${scoreColor};">
      <span class="ats-score-value">${data.score}</span>
      <span class="ats-score-label">${escHtml(t('ats.score_label'))}</span>
    </div>
    <div class="ats-components">`;

  // Component bars
  const compKeys = ['keyword_match', 'section_completeness', 'skill_match', 'content_length', 'format_compliance'];
  const compLabels = {
    keyword_match: t('ats.component_keyword'),
    section_completeness: t('ats.component_section'),
    skill_match: t('ats.component_skill'),
    content_length: t('ats.component_length'),
    format_compliance: t('ats.component_format'),
  };

  for (const key of compKeys) {
    const comp = data.components[key] || {};
    const pct = Math.round((comp.score || 0) * 100);
    const barColor = pct >= 80 ? 'var(--success)' : pct >= 60 ? 'var(--warning)' : 'var(--danger)';
    html += `<div class="ats-component-row">
      <span class="ats-component-label">${escHtml(compLabels[key] || key)}</span>
      <div class="ats-bar-bg"><div class="ats-bar-fill" style="width:${pct}%;background:${barColor};"></div></div>
      <span class="ats-component-pct">${pct}%</span>
    </div>`;
  }
  html += '</div>';

  // Gap analysis
  if (data.missing_keywords?.length || data.missing_skills?.length || data.categories_missing?.length) {
    html += '<div class="ats-gaps">';
    if (data.missing_keywords?.length) {
      html += `<div><strong>${escHtml(t('ats.missing_keywords'))}:</strong> ${data.missing_keywords.map(k => `<span class="badge badge-danger">${escHtml(k)}</span>`).join(' ')}</div>`;
    }
    if (data.missing_skills?.length) {
      html += `<div><strong>${escHtml(t('ats.missing_skills'))}:</strong> ${data.missing_skills.map(k => `<span class="badge badge-danger">${escHtml(k)}</span>`).join(' ')}</div>`;
    }
    if (data.categories_missing?.length) {
      html += `<div><strong>${escHtml(t('ats.categories_missing'))}:</strong> ${data.categories_missing.map(k => `<span class="badge badge-danger">${escHtml(k)}</span>`).join(' ')}</div>`;
    }
    html += '</div>';
  } else {
    html += `<p class="text-success">${escHtml(t('ats.no_gaps'))}</p>`;
  }

  // Matched keywords
  if (data.matched_keywords?.length) {
    html += `<div class="ats-matched"><strong>${escHtml(t('ats.matched_keywords'))}:</strong> ${data.matched_keywords.slice(0, 20).map(k => `<span class="badge badge-success">${escHtml(k)}</span>`).join(' ')}</div>`;
  }

  html += '</div>';
  el.innerHTML = html;
  _applyDataI18n(el);
}

// ---------------------------------------------------------------------------
// Event delegation init
// ---------------------------------------------------------------------------

export function initKnowledgeBase() {
  document.addEventListener('click', e => {
    const editBtn = e.target.closest('[data-kb-edit]');
    if (editBtn) { editKBEntry(parseInt(editBtn.dataset.kbEdit, 10)); return; }

    const deleteBtn = e.target.closest('[data-kb-delete]');
    if (deleteBtn) { deleteKBEntry(parseInt(deleteBtn.dataset.kbDelete, 10)); return; }
  });

  // Escape closes edit overlay
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      const overlay = document.getElementById('kb-edit-overlay');
      if (overlay && !overlay.classList.contains('hidden')) {
        closeKBEdit();
      }
    }
  });
}
