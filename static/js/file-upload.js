/* ═══════════════════════════════════════════════════════════════
   FILE UPLOAD (wizard)
   ═══════════════════════════════════════════════════════════════ */
import { state } from './state.js';
import { escHtml } from './helpers.js';
import { t } from './i18n.js';

export function initFileUpload() {
  const input = document.getElementById('wiz-resume-input');
  const zone = document.getElementById('wiz-resume-zone');

  input.addEventListener('change', () => {
    if (input.files.length) {
      state.wizardData.resume_file = input.files[0];
      zone.classList.add('has-file');
      document.getElementById('wiz-resume-label').innerHTML =
        `<div style="font-size:2rem; margin-bottom:8px;">&#9989;</div>
         <div style="color:var(--success); font-weight:600;">${escHtml(input.files[0].name)}</div>
         <div class="text-dim" style="font-size:.82rem; margin-top:4px;">${t('file_upload.click_to_change')}</div>`;
    }
  });

  // Drag and drop
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.style.borderColor = 'var(--info)'; });
  zone.addEventListener('dragleave', () => { zone.style.borderColor = ''; });
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.style.borderColor = '';
    if (e.dataTransfer.files.length) {
      input.files = e.dataTransfer.files;
      input.dispatchEvent(new Event('change'));
    }
  });
}
