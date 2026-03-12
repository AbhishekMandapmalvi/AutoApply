/* ═══════════════════════════════════════════════════════════════
   RESUME BUILDER — Drag-and-drop KB entry selection + presets
   Implements: TASK-030 M7
   ═══════════════════════════════════════════════════════════════ */

import { t } from './i18n.js';

// ── Helpers ─────────────────────────────────────────────────
function escHtml(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
function escAttr(s) { return String(s).replace(/"/g, '&quot;').replace(/'/g, '&#39;'); }

// ── State ───────────────────────────────────────────────────
let _allEntries = [];
let _selectedEntries = {};   // { category: [entry, ...] }
let _presets = [];
let _currentTemplate = 'classic';
let _onePageMode = false;
const _LINE_LIMIT = 55;     // estimated lines for a 1-page resume

// ── Initialization ──────────────────────────────────────────

export function initResumeBuilder() {
  const search = document.getElementById('rb-kb-search');
  if (search) {
    let timer;
    search.addEventListener('input', () => {
      clearTimeout(timer);
      timer = setTimeout(() => renderKBPanel(search.value), 200);
    });
  }

  const catFilter = document.getElementById('rb-kb-category');
  if (catFilter) {
    catFilter.addEventListener('change', () => {
      const search2 = document.getElementById('rb-kb-search');
      renderKBPanel(search2 ? search2.value : '');
    });
  }

  const tplSelect = document.getElementById('rb-template-select');
  if (tplSelect) {
    tplSelect.addEventListener('change', () => {
      _currentTemplate = tplSelect.value;
    });
  }

  const opToggle = document.getElementById('rb-one-page-toggle');
  if (opToggle) {
    opToggle.addEventListener('change', () => {
      _onePageMode = opToggle.checked;
      updatePageIndicator();
    });
  }
}

// ── Open / Close Builder ────────────────────────────────────

export async function openResumeBuilder() {
  const overlay = document.getElementById('rb-overlay');
  if (!overlay) return;
  overlay.classList.remove('hidden');

  _selectedEntries = {};
  _currentTemplate = 'classic';
  const tplSelect = document.getElementById('rb-template-select');
  if (tplSelect) tplSelect.value = 'classic';

  await Promise.all([loadKBEntries(), loadPresets()]);
  renderKBPanel('');
  renderResumePanel();
  updatePageIndicator();
}

export function closeResumeBuilder() {
  const overlay = document.getElementById('rb-overlay');
  if (overlay) overlay.classList.add('hidden');
}

// ── Load Data ───────────────────────────────────────────────

async function loadKBEntries() {
  try {
    const res = await fetch('/api/kb?limit=2000');
    const data = await res.json();
    _allEntries = data.entries || [];
  } catch {
    _allEntries = [];
  }
}

export async function loadPresets() {
  try {
    const res = await fetch('/api/kb/presets');
    const data = await res.json();
    _presets = data.presets || [];
  } catch {
    _presets = [];
  }
  renderPresetsList();
}

// ── KB Panel (left side) ────────────────────────────────────

function renderKBPanel(search) {
  const container = document.getElementById('rb-kb-entries');
  if (!container) return;

  const catFilter = document.getElementById('rb-kb-category');
  const catValue = catFilter ? catFilter.value : '';
  const term = (search || '').toLowerCase();

  // Get IDs already selected
  const selectedIds = new Set();
  for (const entries of Object.values(_selectedEntries)) {
    for (const e of entries) selectedIds.add(e.id);
  }

  let filtered = _allEntries.filter(e => !selectedIds.has(e.id));

  if (catValue) {
    filtered = filtered.filter(e => e.category === catValue);
  }
  if (term) {
    filtered = filtered.filter(e =>
      (e.text || '').toLowerCase().includes(term) ||
      (e.subsection || '').toLowerCase().includes(term) ||
      (e.category || '').toLowerCase().includes(term)
    );
  }

  if (!filtered.length) {
    container.innerHTML = `<p class="text-muted">${escHtml(t('builder.no_entries'))}</p>`;
    return;
  }

  // Group by category
  const grouped = {};
  for (const e of filtered) {
    const cat = e.category || 'other';
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(e);
  }

  let html = '';
  for (const [cat, entries] of Object.entries(grouped)) {
    html += `<div class="rb-category-group">
      <h4 class="rb-category-header">${escHtml(cat)}</h4>`;
    for (const e of entries) {
      const preview = (e.text || '').substring(0, 80);
      html += `<div class="rb-kb-entry" draggable="true" data-entry-id="${e.id}"
                    role="option" aria-label="${escAttr(cat + ': ' + preview)}"
                    tabindex="0">
        <span class="rb-entry-cat badge">${escHtml(cat)}</span>
        ${e.subsection ? `<strong>${escHtml(e.subsection)}</strong> — ` : ''}
        <span>${escHtml(preview)}${(e.text || '').length > 80 ? '…' : ''}</span>
        <button type="button" class="btn btn-sm rb-add-btn"
                onclick="addToResume(${e.id})" aria-label="${escAttr(t('builder.add_entry'))}"
                title="${escAttr(t('builder.add_entry'))}">+</button>
      </div>`;
    }
    html += '</div>';
  }

  container.innerHTML = html;
  initDragListeners();
}

// ── Resume Panel (right side) ───────────────────────────────

const SECTION_ORDER = ['summary', 'experience', 'skill', 'education', 'project', 'certification'];

function renderResumePanel() {
  for (const section of SECTION_ORDER) {
    const zone = document.getElementById(`rb-drop-${section}`);
    if (!zone) continue;

    const entries = _selectedEntries[section] || [];
    if (!entries.length) {
      zone.innerHTML = `<p class="text-muted rb-drop-placeholder">${escHtml(t('builder.drop_here'))}</p>`;
      continue;
    }

    let html = '';
    for (let i = 0; i < entries.length; i++) {
      const e = entries[i];
      const preview = (e.text || '').substring(0, 100);
      html += `<div class="rb-selected-entry" draggable="true" data-entry-id="${e.id}" data-section="${section}" data-index="${i}"
                    role="listitem" tabindex="0">
        <div class="rb-entry-controls">
          <button type="button" class="btn btn-sm" onclick="moveEntryUp('${section}', ${i})"
                  aria-label="Move up" ${i === 0 ? 'disabled' : ''}>&#x25B2;</button>
          <button type="button" class="btn btn-sm" onclick="moveEntryDown('${section}', ${i})"
                  aria-label="Move down" ${i === entries.length - 1 ? 'disabled' : ''}>&#x25BC;</button>
          <button type="button" class="btn btn-sm rb-remove-btn" onclick="removeFromResume('${section}', ${i})"
                  aria-label="${escAttr(t('builder.remove_entry'))}">&times;</button>
        </div>
        ${e.subsection ? `<strong>${escHtml(e.subsection)}</strong> — ` : ''}
        <span>${escHtml(preview)}${(e.text || '').length > 100 ? '…' : ''}</span>
      </div>`;
    }
    zone.innerHTML = html;
  }

  updatePageIndicator();
}

// ── Page Indicator ──────────────────────────────────────────

function estimateLines() {
  let lines = 5; // header (name, contact)
  for (const section of SECTION_ORDER) {
    const entries = _selectedEntries[section] || [];
    if (!entries.length) continue;
    lines += 2; // section header
    for (const e of entries) {
      const words = (e.text || '').split(/\s+/).length;
      lines += Math.max(1, Math.ceil(words / 12)); // ~12 words per line
      if (e.subsection) lines += 1; // subsection header line
    }
  }
  return lines;
}

function updatePageIndicator() {
  const indicator = document.getElementById('rb-page-indicator');
  if (!indicator) return;

  const lines = estimateLines();
  const totalEntries = Object.values(_selectedEntries).reduce((s, arr) => s + arr.length, 0);

  if (totalEntries === 0) {
    indicator.textContent = t('builder.page_empty');
    indicator.className = 'rb-page-indicator';
    return;
  }

  const pages = Math.ceil(lines / _LINE_LIMIT);

  if (_onePageMode && pages > 1) {
    const excess = lines - _LINE_LIMIT;
    indicator.textContent = t('builder.page_overflow', { pages: pages, excess: excess });
    indicator.className = 'rb-page-indicator rb-page-warning';
  } else {
    indicator.textContent = t('builder.page_count', { pages: pages });
    indicator.className = 'rb-page-indicator rb-page-ok';
  }
}

// ── Add / Remove / Reorder ──────────────────────────────────

export function addToResume(entryId) {
  const entry = _allEntries.find(e => e.id === entryId);
  if (!entry) return;

  const cat = entry.category || 'experience';
  if (!_selectedEntries[cat]) _selectedEntries[cat] = [];

  // Prevent duplicates
  if (_selectedEntries[cat].some(e => e.id === entryId)) return;

  _selectedEntries[cat].push(entry);
  renderKBPanel(document.getElementById('rb-kb-search')?.value || '');
  renderResumePanel();
}

export function removeFromResume(section, index) {
  if (_selectedEntries[section]) {
    _selectedEntries[section].splice(index, 1);
    if (!_selectedEntries[section].length) delete _selectedEntries[section];
  }
  renderKBPanel(document.getElementById('rb-kb-search')?.value || '');
  renderResumePanel();
}

export function moveEntryUp(section, index) {
  const arr = _selectedEntries[section];
  if (!arr || index <= 0) return;
  [arr[index - 1], arr[index]] = [arr[index], arr[index - 1]];
  renderResumePanel();
}

export function moveEntryDown(section, index) {
  const arr = _selectedEntries[section];
  if (!arr || index >= arr.length - 1) return;
  [arr[index], arr[index + 1]] = [arr[index + 1], arr[index]];
  renderResumePanel();
}

// ── Drag & Drop ─────────────────────────────────────────────

function initDragListeners() {
  // KB entries (left panel)
  document.querySelectorAll('.rb-kb-entry[draggable]').forEach(el => {
    el.addEventListener('dragstart', e => {
      e.dataTransfer.setData('text/plain', el.dataset.entryId);
      e.dataTransfer.effectAllowed = 'move';
      el.classList.add('rb-dragging');
    });
    el.addEventListener('dragend', () => el.classList.remove('rb-dragging'));
  });

  // Drop zones
  document.querySelectorAll('.rb-drop-zone').forEach(zone => {
    zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('rb-drop-active'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('rb-drop-active'));
    zone.addEventListener('drop', e => {
      e.preventDefault();
      zone.classList.remove('rb-drop-active');
      const entryId = parseInt(e.dataTransfer.getData('text/plain'), 10);
      if (!isNaN(entryId)) {
        const section = zone.dataset.section;
        // If dropping from another section, remove from old first
        for (const [sec, entries] of Object.entries(_selectedEntries)) {
          const idx = entries.findIndex(en => en.id === entryId);
          if (idx >= 0) {
            entries.splice(idx, 1);
            if (!entries.length) delete _selectedEntries[sec];
            break;
          }
        }
        // Add to target section
        const entry = _allEntries.find(en => en.id === entryId);
        if (entry) {
          if (!_selectedEntries[section]) _selectedEntries[section] = [];
          if (!_selectedEntries[section].some(en => en.id === entryId)) {
            _selectedEntries[section].push(entry);
          }
        }
        renderKBPanel(document.getElementById('rb-kb-search')?.value || '');
        renderResumePanel();
      }
    });
  });
}

// ── Presets ──────────────────────────────────────────────────

function renderPresetsList() {
  const container = document.getElementById('rb-presets-list');
  if (!container) return;

  if (!_presets.length) {
    container.innerHTML = `<p class="text-muted">${escHtml(t('builder.no_presets'))}</p>`;
    return;
  }

  let html = '';
  for (const p of _presets) {
    const ids = typeof p.entry_ids === 'string' ? JSON.parse(p.entry_ids) : (p.entry_ids || []);
    html += `<div class="rb-preset-card" role="listitem">
      <div class="rb-preset-info">
        <strong>${escHtml(p.name)}</strong>
        <span class="text-muted">${ids.length} ${escHtml(t('builder.entries'))} · ${escHtml(p.template || 'classic')}</span>
      </div>
      <div class="rb-preset-actions">
        <button type="button" class="btn btn-sm btn-primary" onclick="loadPreset(${p.id})"
                aria-label="${escAttr(t('builder.load_preset'))}">${escHtml(t('builder.load'))}</button>
        <button type="button" class="btn btn-sm" onclick="deletePreset(${p.id})"
                aria-label="${escAttr(t('builder.delete_preset'))}">&times;</button>
      </div>
    </div>`;
  }
  container.innerHTML = html;
}

export async function savePreset() {
  const nameInput = document.getElementById('rb-preset-name');
  const name = nameInput ? nameInput.value.trim() : '';
  if (!name) return;

  const entryIds = [];
  for (const section of SECTION_ORDER) {
    for (const e of (_selectedEntries[section] || [])) {
      entryIds.push(e.id);
    }
  }

  if (!entryIds.length) return;

  try {
    const res = await fetch('/api/kb/presets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, entry_ids: entryIds, template: _currentTemplate }),
    });
    if (res.ok) {
      if (nameInput) nameInput.value = '';
      await loadPresets();
    }
  } catch {
    // Logged by fetch interceptor
  }
}

export async function loadPreset(presetId) {
  const preset = _presets.find(p => p.id === presetId);
  if (!preset) return;

  const ids = typeof preset.entry_ids === 'string' ? JSON.parse(preset.entry_ids) : (preset.entry_ids || []);

  // Fetch entries by IDs if not already loaded
  if (!_allEntries.length) await loadKBEntries();

  _selectedEntries = {};
  for (const id of ids) {
    const entry = _allEntries.find(e => e.id === id);
    if (entry) {
      const cat = entry.category || 'experience';
      if (!_selectedEntries[cat]) _selectedEntries[cat] = [];
      _selectedEntries[cat].push(entry);
    }
  }

  _currentTemplate = preset.template || 'classic';
  const tplSelect = document.getElementById('rb-template-select');
  if (tplSelect) tplSelect.value = _currentTemplate;

  renderKBPanel(document.getElementById('rb-kb-search')?.value || '');
  renderResumePanel();
}

export async function deletePreset(presetId) {
  try {
    const res = await fetch(`/api/kb/presets/${presetId}`, { method: 'DELETE' });
    if (res.ok) await loadPresets();
  } catch {
    // Logged by fetch interceptor
  }
}

// ── Preview PDF ─────────────────────────────────────────────

export async function previewBuilderResume() {
  const entryIds = [];
  for (const section of SECTION_ORDER) {
    for (const e of (_selectedEntries[section] || [])) {
      entryIds.push(e.id);
    }
  }
  if (!entryIds.length) return;

  const statusEl = document.getElementById('rb-preview-status');
  if (statusEl) statusEl.textContent = t('builder.generating');

  try {
    const res = await fetch('/api/kb/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ entry_ids: entryIds, template: _currentTemplate }),
    });

    if (!res.ok) {
      if (statusEl) statusEl.textContent = t('builder.preview_error');
      return;
    }

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const iframe = document.getElementById('rb-preview-iframe');
    if (iframe) {
      iframe.src = url;
      iframe.classList.remove('hidden');
    }
    if (statusEl) statusEl.textContent = '';
  } catch {
    if (statusEl) statusEl.textContent = t('builder.preview_error');
  }
}

// ── Auto-fill from JD ───────────────────────────────────────

export async function autoFillFromJD() {
  const jdInput = document.getElementById('rb-autofill-jd');
  const jdText = jdInput ? jdInput.value.trim() : '';
  if (!jdText) return;

  const statusEl = document.getElementById('rb-autofill-status');
  if (statusEl) statusEl.textContent = t('builder.autofilling');

  try {
    // Score all entries against JD
    const res = await fetch('/api/kb/ats-score', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ jd_text: jdText }),
    });

    if (!res.ok) {
      if (statusEl) statusEl.textContent = '';
      return;
    }

    const data = await res.json();
    const matchedKeywords = new Set((data.matched_keywords || []).map(k => k.toLowerCase()));
    const matchedSkills = new Set((data.matched_skills || []).map(s => s.toLowerCase()));

    // Score each entry by how many matched terms it contains
    const scored = _allEntries.map(e => {
      const text = ((e.text || '') + ' ' + (e.subsection || '')).toLowerCase();
      let score = 0;
      for (const kw of matchedKeywords) { if (text.includes(kw)) score += 2; }
      for (const sk of matchedSkills) { if (text.includes(sk)) score += 3; }
      return { entry: e, score };
    }).filter(s => s.score > 0).sort((a, b) => b.score - a.score);

    // Auto-select top entries by category
    _selectedEntries = {};
    const limits = { experience: 5, skill: 2, education: 2, summary: 1, project: 3, certification: 2 };

    for (const { entry } of scored) {
      const cat = entry.category || 'experience';
      const limit = limits[cat] || 3;
      if (!_selectedEntries[cat]) _selectedEntries[cat] = [];
      if (_selectedEntries[cat].length < limit && !_selectedEntries[cat].some(e => e.id === entry.id)) {
        _selectedEntries[cat].push(entry);
      }
    }

    renderKBPanel(document.getElementById('rb-kb-search')?.value || '');
    renderResumePanel();
    if (statusEl) statusEl.textContent = '';
  } catch {
    if (statusEl) statusEl.textContent = '';
  }
}
