/* ═══════════════════════════════════════════════════════════════
   API — Shared fetch wrapper and HTML utilities
   ═══════════════════════════════════════════════════════════════ */
import { escHtml } from './helpers.js';

/**
 * Fetch wrapper that parses JSON responses and throws on non-OK status.
 * Auth headers are injected by auth.js (patches window.fetch).
 * @param {string} url
 * @param {RequestInit} [opts]
 * @returns {Promise<any>}
 */
export async function apiFetch(url, opts = {}) {
  const res = await fetch(url, opts);
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${text}`);
  }
  const ct = res.headers.get('content-type') || '';
  if (ct.includes('application/json')) {
    return res.json();
  }
  return res;
}

// Re-export escHtml for modules that import both from api.js
export { escHtml };
