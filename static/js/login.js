/* ═══════════════════════════════════════════════════════════════
   PLATFORM LOGIN BROWSER
   ═══════════════════════════════════════════════════════════════ */
import { t } from './i18n.js';

export async function openLoginBrowser(url) {
  try {
    const res = await fetch('/api/login/open', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ url }),
    });
    const data = await res.json();
    if (!res.ok) {
      alert(data.error || t('login.open_error'));
      return;
    }
    // Show the close button, update login button states
    updateLoginUI(true);
    // Poll until browser is closed externally
    pollLoginStatus();
  } catch (e) {
    alert(t('login.connection_error'));
  }
}

export async function closeLoginBrowser() {
  try {
    await fetch('/api/login/close', { method: 'POST' });
  } catch { }
  updateLoginUI(false);
  setTimeout(checkLoginSessions, 500);
}

function updateLoginUI(isOpen) {
  // Wizard buttons
  const linkedinBtn = document.getElementById('wizard-linkedin-login');
  const indeedBtn = document.getElementById('wizard-indeed-login');
  const closeBtn = document.getElementById('wizard-close-browser');
  if (linkedinBtn) linkedinBtn.disabled = isOpen;
  if (indeedBtn) indeedBtn.disabled = isOpen;
  if (closeBtn) closeBtn.classList.toggle('hidden', !isOpen);

  // Settings buttons
  const sLinkedin = document.getElementById('settings-linkedin-login');
  const sIndeed = document.getElementById('settings-indeed-login');
  const sClose = document.getElementById('settings-close-browser');
  if (sLinkedin) sLinkedin.disabled = isOpen;
  if (sIndeed) sIndeed.disabled = isOpen;
  if (sClose) sClose.classList.toggle('hidden', !isOpen);
}

function pollLoginStatus() {
  const iv = setInterval(async () => {
    try {
      const res = await fetch('/api/login/status');
      const data = await res.json();
      if (!data.open) {
        clearInterval(iv);
        updateLoginUI(false);
        checkLoginSessions();
      }
    } catch {
      clearInterval(iv);
      updateLoginUI(false);
    }
  }, 2000);
}

export async function checkLoginSessions() {
  try {
    const res = await fetch('/api/login/sessions');
    if (!res.ok) return;
    const data = await res.json();
    const ids = [
      { id: 'linkedin-session-status', connected: data.linkedin },
      { id: 'indeed-session-status',   connected: data.indeed },
      { id: 'wiz-linkedin-session',    connected: data.linkedin },
      { id: 'wiz-indeed-session',      connected: data.indeed },
    ];
    for (const { id, connected } of ids) {
      const el = document.getElementById(id);
      if (!el) continue;
      if (connected) {
        el.innerHTML = '<span class="dot dot-green"></span> ' + t('login.connected');
        el.className = 'status-badge ok';
        el.style.fontSize = '.8rem';
      } else {
        el.innerHTML = '<span class="dot dot-gray"></span> ' + t('login.not_connected');
        el.className = 'status-badge';
        el.style.fontSize = '.8rem';
      }
    }
  } catch { }
}
