/* ═══════════════════════════════════════════════════════════════
   AI PROVIDER STATUS
   ═══════════════════════════════════════════════════════════════ */
import { state } from './state.js';
import { t } from './i18n.js';

export function updateAIIndicators() {
  const cls = state.aiAvailable ? 'dot dot-green' : 'dot dot-yellow';
  const txt = state.aiAvailable ? t('ai.connected') : t('ai.not_configured');
  document.querySelectorAll('#nav-ai-indicator, #profile-ai-indicator').forEach(el => {
    const dot = el.querySelector('.dot');
    const span = el.querySelector('span:last-child');
    if (dot) dot.className = cls;
    if (span) span.textContent = txt;
  });
}
