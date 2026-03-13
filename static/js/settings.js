/* ═══════════════════════════════════════════════════════════════
   SETTINGS
   ═══════════════════════════════════════════════════════════════ */
import { state } from './state.js';
import { setTags } from './tag-input.js';
import { checkLoginSessions } from './login.js';
import { t, getLocale, setLocale } from './i18n.js';
import { updateAIIndicators } from './ai-status.js';

const LLM_DEFAULT_MODELS = {
  anthropic: 'claude-sonnet-4-20250514',
  openai: 'gpt-4o',
  google: 'gemini-2.0-flash',
  deepseek: 'deepseek-chat',
};

/** Human-readable names for locale codes (FR-134). */
const LOCALE_NAMES = {
  en: 'English',
  es: 'Español',
  fr: 'Français',
  de: 'Deutsch',
  pt: 'Português',
  ja: '日本語',
  zh: '中文',
  ko: '한국어',
};

export async function loadSettings() {
  try {
    const res = await fetch('/api/config');
    const cfg = await res.json();
    const p = cfg.profile || {};
    const pr = cfg.search_criteria || {};

    document.getElementById('set-first-name').value = p.first_name || '';
    document.getElementById('set-last-name').value  = p.last_name || '';
    document.getElementById('set-email').value      = p.email || '';
    document.getElementById('set-phone-code').value = p.phone_country_code || '+1';
    document.getElementById('set-phone').value      = p.phone || '';
    document.getElementById('set-address1').value   = p.address_line1 || '';
    document.getElementById('set-address2').value   = p.address_line2 || '';
    document.getElementById('set-city').value       = p.city || '';
    document.getElementById('set-state').value      = p.state || '';
    document.getElementById('set-zip').value        = p.zip_code || '';
    document.getElementById('set-country').value    = p.country || 'United States';
    document.getElementById('set-bio').value        = p.bio || '';
    document.getElementById('set-linkedin').value   = p.linkedin_url || '';
    document.getElementById('set-portfolio').value  = p.portfolio_url || '';

    // Screening answers
    const sa = p.screening_answers || {};
    document.getElementById('set-work-authorization').value = sa.work_authorization || '';
    document.getElementById('set-visa-sponsorship').value   = sa.visa_sponsorship || '';
    document.getElementById('set-years-experience').value   = sa.years_experience || '';
    document.getElementById('set-desired-salary').value     = sa.desired_salary || '';
    document.getElementById('set-willing-relocate').value   = sa.willing_to_relocate || '';
    document.getElementById('set-start-date').value         = sa.start_date || '';
    document.getElementById('set-eeo-gender').value         = sa.gender || '';
    document.getElementById('set-eeo-ethnicity').value      = sa.ethnicity || '';
    document.getElementById('set-eeo-veteran').value        = sa.veteran_status || '';
    document.getElementById('set-eeo-disability').value     = sa.disability_status || '';

    // LLM config
    const llm = cfg.llm || {};
    document.getElementById('set-llm-provider').value = llm.provider || '';
    document.getElementById('set-llm-model').value    = llm.model || '';
    document.getElementById('set-llm-api-key').value  = llm.api_key || '';
    onLLMProviderChange();

    setTags('set-titles-tags',    pr.job_titles || []);
    setTags('set-locations-tags', pr.locations || []);
    document.getElementById('set-remote').checked = !!pr.remote_only;
    document.getElementById('set-salary').value   = pr.salary_min || '';
    setTags('set-include-tags', pr.keywords_include || []);
    setTags('set-exclude-tags', pr.keywords_exclude || []);

    document.querySelectorAll('.set-exp-level').forEach(cb => {
      cb.checked = (pr.experience_levels || []).includes(cb.value);
    });

    // Schedule
    const sched = (cfg.bot || {}).schedule || {};
    document.getElementById('set-schedule-enabled').checked = !!sched.enabled;
    const schedDays = sched.days_of_week || ['mon','tue','wed','thu','fri'];
    document.querySelectorAll('.set-schedule-day').forEach(cb => {
      cb.checked = schedDays.includes(cb.value);
    });
    document.getElementById('set-schedule-start').value = sched.start_time || '09:00';
    document.getElementById('set-schedule-end').value = sched.end_time || '17:00';
    updateScheduleUI();
    checkLoginSessions();
    _loadLocaleDropdown();
  } catch { }
}

/** Populate locale dropdown from GET /api/locales (FR-131). */
async function _loadLocaleDropdown() {
  const sel = document.getElementById('set-locale');
  if (!sel) return;
  try {
    const res = await fetch('/api/locales');
    const data = await res.json();
    sel.innerHTML = '';
    for (const code of data.available || []) {
      const opt = document.createElement('option');
      opt.value = code;
      opt.textContent = LOCALE_NAMES[code] || code;
      sel.appendChild(opt);
    }
    sel.value = getLocale();
  } catch {
    // If endpoint unavailable, show current locale only
    sel.innerHTML = `<option value="${getLocale()}">${LOCALE_NAMES[getLocale()] || getLocale()}</option>`;
  }
}

/** Handle locale dropdown change (FR-131, FR-132, FR-133). */
export async function onLocaleChange() {
  const sel = document.getElementById('set-locale');
  if (!sel) return;
  await setLocale(sel.value);
}

function _collectScreeningAnswers() {
  const ans = {};
  const fields = {
    'set-work-authorization': 'work_authorization',
    'set-visa-sponsorship':   'visa_sponsorship',
    'set-years-experience':   'years_experience',
    'set-desired-salary':     'desired_salary',
    'set-willing-relocate':   'willing_to_relocate',
    'set-start-date':         'start_date',
    'set-eeo-gender':         'gender',
    'set-eeo-ethnicity':      'ethnicity',
    'set-eeo-veteran':        'veteran_status',
    'set-eeo-disability':     'disability_status',
  };
  for (const [id, key] of Object.entries(fields)) {
    const val = document.getElementById(id).value;
    if (val) ans[key] = val;
  }
  return ans;
}

export async function saveSettings() {
  const config = {
    profile: {
      first_name:         document.getElementById('set-first-name').value,
      last_name:          document.getElementById('set-last-name').value,
      email:              document.getElementById('set-email').value,
      phone_country_code: document.getElementById('set-phone-code').value || '+1',
      phone:              document.getElementById('set-phone').value,
      address_line1:      document.getElementById('set-address1').value,
      address_line2:      document.getElementById('set-address2').value,
      city:               document.getElementById('set-city').value,
      state:              document.getElementById('set-state').value,
      zip_code:           document.getElementById('set-zip').value,
      country:            document.getElementById('set-country').value || 'United States',
      bio:                document.getElementById('set-bio').value,
      linkedin_url:       document.getElementById('set-linkedin').value,
      portfolio_url:      document.getElementById('set-portfolio').value,
      screening_answers:  _collectScreeningAnswers(),
    },
    llm: {
      provider: document.getElementById('set-llm-provider').value,
      api_key:  document.getElementById('set-llm-api-key').value,
      model:    document.getElementById('set-llm-model').value,
    },
    search_criteria: {
      job_titles:        state.tagInputs['set-titles-tags'] || [],
      locations:         state.tagInputs['set-locations-tags'] || [],
      remote_only:       document.getElementById('set-remote').checked,
      salary_min:        parseInt(document.getElementById('set-salary').value) || null,
      keywords_include:  state.tagInputs['set-include-tags'] || [],
      keywords_exclude:  state.tagInputs['set-exclude-tags'] || [],
      experience_levels: [...document.querySelectorAll('.set-exp-level:checked')].map(c => c.value),
    },
  };

  try {
    await fetch('/api/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });

    // Save schedule separately via dedicated endpoint
    const schedData = {
      enabled:      document.getElementById('set-schedule-enabled').checked,
      days_of_week: [...document.querySelectorAll('.set-schedule-day:checked')].map(c => c.value),
      start_time:   document.getElementById('set-schedule-start').value,
      end_time:     document.getElementById('set-schedule-end').value,
    };
    await fetch('/api/bot/schedule', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(schedData),
    });
    updateScheduleUI();

    // Refresh AI availability indicator after config change
    try {
      const statusRes = await fetch('/api/setup/status');
      const statusData = await statusRes.json();
      state.aiAvailable = !!statusData.ai_available;
      updateAIIndicators();
      const banner = document.getElementById('ai-warning-banner');
      if (banner) banner.classList.toggle('hidden', state.aiAvailable);
    } catch { /* non-critical */ }

    const msg = document.getElementById('settings-saved-msg');
    msg.classList.remove('hidden');
    setTimeout(() => msg.classList.add('hidden'), 2500);
  } catch {
    alert(t('settings.save_error'));
  }
}

export function updateScheduleUI() {
  const enabled = document.getElementById('set-schedule-enabled').checked;
  const badge = document.getElementById('schedule-status-badge');
  if (enabled) {
    badge.classList.remove('hidden');
  } else {
    badge.classList.add('hidden');
  }
}

export async function changeApplyMode(mode) {
  try {
    await fetch('/api/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bot: { apply_mode: mode } }),
    });
  } catch (e) {
    console.warn('Could not save apply_mode:', e);
  }
}

export function initBotToggles() {
  const adaptive = document.getElementById('set-adaptive-resume');
  const coverLetter = document.getElementById('set-cover-letter');
  if (adaptive) {
    adaptive.addEventListener('change', () => {
      fetch('/api/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ resume_reuse: { enabled: adaptive.checked } }),
      }).catch(e => console.warn('Could not save adaptive resume:', e));
    });
  }
  if (coverLetter) {
    coverLetter.addEventListener('change', () => {
      fetch('/api/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bot: { cover_letter_enabled: coverLetter.checked } }),
      }).catch(e => console.warn('Could not save cover letter:', e));
    });
  }
}

export async function loadApplyMode() {
  try {
    const res = await fetch('/api/config');
    const cfg = await res.json();
    const mode = (cfg.bot && cfg.bot.apply_mode) || 'full_auto';
    const sel = document.getElementById('apply-mode-select');
    if (sel) sel.value = mode;

    // Load bot toggles on dashboard
    const adaptive = document.getElementById('set-adaptive-resume');
    const coverLetter = document.getElementById('set-cover-letter');
    if (adaptive) adaptive.checked = (cfg.resume_reuse || {}).enabled !== false;
    if (coverLetter) coverLetter.checked = (cfg.bot || {}).cover_letter_enabled !== false;
  } catch { }
}

// ---------------------------------------------------------------------------
// Default Resume
// ---------------------------------------------------------------------------

export async function uploadDefaultResume(input) {
  const file = input.files?.[0];
  if (!file) return;
  const form = new FormData();
  form.append('file', file);
  try {
    const res = await fetch('/api/config/default-resume', { method: 'POST', body: form });
    const data = await res.json();
    if (data.success) {
      _updateDefaultResumeUI(data.filename);
    } else {
      alert(data.error || 'Upload failed');
    }
  } catch (e) {
    console.warn('Default resume upload failed:', e);
  }
  input.value = '';
}

export async function removeDefaultResume() {
  try {
    await fetch('/api/config/default-resume', { method: 'DELETE' });
    _updateDefaultResumeUI(null);
  } catch (e) {
    console.warn('Default resume remove failed:', e);
  }
}

export async function loadDefaultResume() {
  try {
    const res = await fetch('/api/config/default-resume');
    const data = await res.json();
    _updateDefaultResumeUI(data.filename);
  } catch { }
}

function _updateDefaultResumeUI(filename) {
  const nameEl = document.getElementById('default-resume-name');
  const removeBtn = document.getElementById('btn-remove-default-resume');
  if (nameEl) nameEl.textContent = filename || 'None';
  if (removeBtn) removeBtn.classList.toggle('hidden', !filename);
}

export function onLLMProviderChange() {
  const provider = document.getElementById('set-llm-provider').value;
  const modelInput = document.getElementById('set-llm-model');
  if (provider && !modelInput.value) {
    modelInput.placeholder = LLM_DEFAULT_MODELS[provider] || '';
  }
  document.getElementById('llm-key-status').textContent = '';
}

export async function validateLLMKey() {
  const provider = document.getElementById('set-llm-provider').value;
  const apiKey   = document.getElementById('set-llm-api-key').value;
  const model    = document.getElementById('set-llm-model').value;
  const status   = document.getElementById('llm-key-status');
  const btn      = document.getElementById('btn-validate-key');

  if (!provider) { status.textContent = t('settings.select_provider'); status.style.color = '#f87171'; return; }
  if (!apiKey)   { status.textContent = t('settings.enter_api_key'); status.style.color = '#f87171'; return; }

  btn.disabled = true;
  btn.textContent = t('settings.validating');
  status.textContent = '';

  try {
    const res = await fetch('/api/ai/validate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider, api_key: apiKey, model: model || undefined }),
    });
    const data = await res.json();
    if (data.valid) {
      status.textContent = t('settings.key_valid');
      status.style.color = '#34d399';
      // Auto-save the validated key so it persists immediately
      try {
        await fetch('/api/config', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ llm: { provider, api_key: apiKey, model: model || '' } }),
        });
        state.aiAvailable = true;
        updateAIIndicators();
        const banner = document.getElementById('ai-warning-banner');
        if (banner) banner.classList.toggle('hidden', true);
      } catch { /* save failed silently — user can still use main Save */ }
    } else {
      status.textContent = t('settings.key_invalid');
      status.style.color = '#f87171';
    }
  } catch {
    status.textContent = t('settings.validation_failed');
    status.style.color = '#f87171';
  } finally {
    btn.disabled = false;
    btn.textContent = t('button.validate');
  }
}
