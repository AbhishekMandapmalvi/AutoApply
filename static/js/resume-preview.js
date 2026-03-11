/* ═══════════════════════════════════════════════════════════════
   RESUME PREVIEW — Preview assembled resumes from KB entries
   ═══════════════════════════════════════════════════════════════ */

import { t, _applyDataI18n } from './i18n.js';
import { escHtml, escAttr } from './helpers.js';

// ---------------------------------------------------------------------------
// Preview resume from KB entries
// ---------------------------------------------------------------------------

export async function previewKBResume() {
  const templateSelect = document.getElementById('kb-preview-template');
  const jdTextarea = document.getElementById('kb-preview-jd');
  const template = templateSelect?.value || 'classic';
  const jdText = jdTextarea?.value?.trim() || '';

  if (!jdText) {
    const statusEl = document.getElementById('kb-preview-status');
    if (statusEl) {
      statusEl.textContent = t('errors.invalid_request');
      statusEl.className = 'text-danger';
    }
    return;
  }

  const statusEl = document.getElementById('kb-preview-status');
  if (statusEl) {
    statusEl.textContent = t('kb.upload_processing');
    statusEl.className = 'text-info';
  }

  try {
    const res = await fetch('/api/kb/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ template, jd_text: jdText }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      const msg = err.description || err.message || 'Preview failed';
      if (statusEl) {
        statusEl.textContent = msg;
        statusEl.className = 'text-danger';
      }
      return;
    }

    // Response is a PDF — show in iframe
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    showPreviewPDF(url, template);

    if (statusEl) {
      statusEl.textContent = '';
      statusEl.className = '';
    }
  } catch (e) {
    if (statusEl) {
      statusEl.textContent = e.message;
      statusEl.className = 'text-danger';
    }
  }
}

function showPreviewPDF(url, template) {
  const overlay = document.getElementById('kb-preview-overlay');
  if (!overlay) return;

  const content = overlay.querySelector('.kb-preview-content') || overlay;
  content.innerHTML = `
    <div class="resume-detail-header">
      <button type="button" class="btn btn-secondary" onclick="closeKBPreview()"
              data-i18n="resumes.back_to_library">Back</button>
      <h3>${escHtml(t('reuse.settings_title'))} — ${escHtml(template)}</h3>
      <a href="${escAttr(url)}" download="preview_${escAttr(template)}.pdf"
         class="btn btn-primary">Download PDF</a>
    </div>
    <iframe src="${escAttr(url)}" class="resume-pdf-preview"
            title="Resume preview" style="width:100%;height:80vh;border:none;"></iframe>
  `;
  _applyDataI18n(content);
  overlay.classList.remove('hidden');
}

export function closeKBPreview() {
  const overlay = document.getElementById('kb-preview-overlay');
  if (overlay) {
    // Revoke blob URL to free memory
    const iframe = overlay.querySelector('iframe');
    if (iframe?.src?.startsWith('blob:')) URL.revokeObjectURL(iframe.src);
    overlay.classList.add('hidden');
  }
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

export function initResumePreview() {
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      const overlay = document.getElementById('kb-preview-overlay');
      if (overlay && !overlay.classList.contains('hidden')) {
        closeKBPreview();
      }
    }
  });
}
