/* ═══════════════════════════════════════════════════════════════
   PROFILE (Experience Files)
   ═══════════════════════════════════════════════════════════════ */
import { state } from './state.js';
import { escHtml, escAttr } from './helpers.js';
import { closeModal, openModal } from './modals.js';
import { t } from './i18n.js';

export async function loadProfileFiles() {
  const grid = document.getElementById('profile-file-grid');
  try {
    const res = await fetch('/api/profile/experiences');
    const data = await res.json();
    const files = data.files || [];
    state.profileFiles = files;

    if (!files.length) {
      grid.innerHTML = `<div class="text-center text-dim" style="padding:40px 0; grid-column:1/-1;">${t('profile.no_files')}</div>`;
      return;
    }

    grid.innerHTML = files.map(f => {
      const wordCount = (f.content || '').split(/\s+/).filter(w => w).length;
      const preview = (f.content || '').slice(0, 100);
      return `
      <div class="file-card">
        <h4>${escHtml(f.name)}</h4>
        <div class="meta">
          <span>${wordCount} ${t('profile.words')}</span>
          <span>${f.modified_at ? new Date(f.modified_at).toLocaleDateString() : ''}</span>
        </div>
        <div class="preview">${escHtml(preview)}${preview.length >= 100 ? '...' : ''}</div>
        <div class="actions">
          <button class="btn btn-ghost btn-sm" data-edit-file="${escAttr(f.name)}">${t('button.edit')}</button>
          <button class="btn btn-danger btn-sm" data-delete-file="${escAttr(f.name)}">${t('button.delete')}</button>
        </div>
      </div>`;
    }).join('');
  } catch {
    grid.innerHTML = `<div class="text-center text-dim" style="padding:40px 0; grid-column:1/-1;">${t('profile.load_error')}</div>`;
  }
}

export function showFileModal(filename) {
  state.editingFile = filename || null;
  document.getElementById('modal-file-title').textContent = filename ? t('profile.edit_file') : t('profile.new_file');
  document.getElementById('modal-file-name').value = filename || '';
  document.getElementById('modal-file-name').disabled = !!filename;
  document.getElementById('modal-file-content').value = '';

  if (filename) {
    const cached = state.profileFiles.find(f => f.name === filename);
    if (cached) {
      document.getElementById('modal-file-content').value = cached.content || '';
    }
  }

  openModal('modal-file-edit');
}

export function editFile(filename) { showFileModal(filename); }

export async function saveFile() {
  const filename = document.getElementById('modal-file-name').value.trim();
  const content  = document.getElementById('modal-file-content').value;
  if (!filename) { alert(t('profile.enter_filename')); return; }

  const method = state.editingFile ? 'PUT' : 'POST';
  const url = state.editingFile
    ? `/api/profile/experiences/${encodeURIComponent(state.editingFile)}`
    : '/api/profile/experiences';

  try {
    await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename, content }),
    });
    closeModal('modal-file-edit');
    loadProfileFiles();
  } catch (e) {
    alert(t('profile.save_error'));
  }
}

export function confirmDeleteFile(filename) {
  openModal('modal-confirm-delete');
  document.getElementById('btn-confirm-delete').onclick = async () => {
    try {
      await fetch(`/api/profile/experiences/${encodeURIComponent(filename)}`, { method: 'DELETE' });
    } catch { }
    closeModal('modal-confirm-delete');
    loadProfileFiles();
  };
}
