/* ═══════════════════════════════════════════════════════════════
   TAG INPUT SYSTEM — with ARIA and keyboard support (WCAG 2.1)
   ═══════════════════════════════════════════════════════════════ */
import { state } from './state.js';
import { escHtml } from './helpers.js';
import { t } from './i18n.js';

export function initTagInputs() {
  document.querySelectorAll('.tag-input-wrap').forEach(wrap => {
    const id = wrap.id;
    state.tagInputs[id] = [];
    const input = document.createElement('input');
    input.type = 'text';
    input.placeholder = wrap.dataset.placeholder || t('placeholder.tag_input');
    input.setAttribute('aria-label', wrap.dataset.placeholder || t('placeholder.tag_input'));
    wrap.appendChild(input);
    wrap.addEventListener('click', () => input.focus());

    input.addEventListener('keydown', e => {
      if (e.key === 'Enter' && input.value.trim()) {
        e.preventDefault();
        _addFromInput(id, input);
      }
      if (e.key === 'Backspace' && !input.value && state.tagInputs[id].length) {
        removeTag(id, state.tagInputs[id].length - 1);
      }
    });
    // Also add on comma for quick multi-add
    input.addEventListener('input', () => {
      const v = input.value;
      if (v.includes(',')) {
        const parts = v.split(',');
        // Add all complete parts (before last comma)
        parts.slice(0, -1).forEach(p => {
          const t = p.trim();
          if (t) addTag(id, t);
        });
        // Keep the part after last comma as ongoing input
        input.value = parts[parts.length - 1];
      }
    });
  });

  // Event delegation for tag remove buttons (keyboard + click)
  document.addEventListener('click', e => {
    const btn = e.target.closest('.tag-remove');
    if (btn) {
      const wrapperId = btn.dataset.wrapper;
      const idx = parseInt(btn.dataset.idx, 10);
      removeTag(wrapperId, idx);
    }
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') {
      const btn = e.target.closest('.tag-remove');
      if (btn) {
        e.preventDefault();
        const wrapperId = btn.dataset.wrapper;
        const idx = parseInt(btn.dataset.idx, 10);
        removeTag(wrapperId, idx);
      }
    }
  });
}

function _addFromInput(wrapperId, input) {
  const text = input.value.trim().replace(/,+$/, '').trim();
  if (text) {
    addTag(wrapperId, text);
    input.value = '';
  }
}

export function addTagFromInput(wrapperId) {
  const wrap = document.getElementById(wrapperId);
  const input = wrap.querySelector('input');
  _addFromInput(wrapperId, input);
  input.focus();
}

export function addTag(wrapperId, text) {
  if (!text || state.tagInputs[wrapperId].includes(text)) return;
  state.tagInputs[wrapperId].push(text);
  renderTags(wrapperId);
  updateSuggestions(wrapperId);
}

export function removeTag(wrapperId, idx) {
  state.tagInputs[wrapperId].splice(idx, 1);
  renderTags(wrapperId);
  updateSuggestions(wrapperId);
  // Return focus to the input after removing
  const wrap = document.getElementById(wrapperId);
  if (wrap) {
    const input = wrap.querySelector('input');
    if (input) input.focus();
  }
}

export function renderTags(wrapperId) {
  const wrap = document.getElementById(wrapperId);
  const input = wrap.querySelector('input');
  wrap.querySelectorAll('.tag').forEach(t => t.remove());
  state.tagInputs[wrapperId].forEach((text, idx) => {
    const tag = document.createElement('span');
    tag.className = 'tag';
    tag.innerHTML = `${escHtml(text)} <span class="tag-remove" role="button" tabindex="0" aria-label="Remove ${escHtml(text)}" data-wrapper="${wrapperId}" data-idx="${idx}">&times;</span>`;
    wrap.insertBefore(tag, input);
  });
}

export function setTags(wrapperId, arr) {
  state.tagInputs[wrapperId] = Array.isArray(arr) ? [...arr] : [];
  renderTags(wrapperId);
  updateSuggestions(wrapperId);
}

export function updateSuggestions(wrapperId) {
  // Hide suggestion chips that are already added
  document.querySelectorAll(`.tag-suggestions[data-for="${wrapperId}"] .tag-suggestion`).forEach(chip => {
    const text = chip.textContent.trim();
    chip.style.display = state.tagInputs[wrapperId].includes(text) ? 'none' : '';
  });
}
