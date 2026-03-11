/* ═══════════════════════════════════════════════════════════════
   WIZARD
   ═══════════════════════════════════════════════════════════════ */
import { state } from './state.js';
import { escHtml } from './helpers.js';
import { showApp } from './navigation.js';
import { checkLoginSessions, closeLoginBrowser } from './login.js';
import { t } from './i18n.js';

export function showWizard(setupData) {
  document.getElementById('wizard-overlay').classList.remove('hidden');
  document.getElementById('navbar').classList.add('hidden');
  document.getElementById('app-screens').classList.add('hidden');

  // AI status badge
  const badge = document.getElementById('wizard-ai-status');
  if (setupData && setupData.ai_available) {
    badge.className = 'status-badge ok';
    badge.innerHTML = '<span class="dot dot-green"></span> ' + t('wizard.ai_configured');
  } else {
    badge.className = 'status-badge warn';
    badge.innerHTML = '<span class="dot dot-yellow"></span> ' + t('wizard.ai_not_configured');
  }

  // Build progress dots
  const prog = document.getElementById('wizard-progress');
  prog.innerHTML = '';
  for (let i = 0; i < 7; i++) {
    const d = document.createElement('div');
    d.className = 'step-dot' + (i === 0 ? ' active' : '');
    prog.appendChild(d);
  }

  setWizardStep(0);
  wizardRefreshFiles();
}

export function setWizardStep(n) {
  state.wizardStep = n;
  document.querySelectorAll('.wizard-step').forEach(s => s.classList.remove('active'));
  const step = document.querySelector(`.wizard-step[data-step="${n}"]`);
  if (step) step.classList.add('active');

  // Update progress dots and aria
  const progress = document.getElementById('wizard-progress');
  if (progress) progress.setAttribute('aria-valuenow', n + 1);
  document.querySelectorAll('.wizard-progress .step-dot').forEach((d, i) => {
    d.className = 'step-dot' + (i < n ? ' done' : '') + (i === n ? ' active' : '');
  });

  // Build summary on last step
  if (n === 6) buildWizardSummary();
  // Check login sessions when entering Platform Login step
  if (n === 5) checkLoginSessions();
}

export function wizardNext() {
  if (state.wizardStep < 6) setWizardStep(state.wizardStep + 1);
}

export function wizardPrev() {
  if (state.wizardStep > 0) setWizardStep(state.wizardStep - 1);
}

export async function wizardRefreshFiles() {
  try {
    const res = await fetch('/api/profile/status');
    const data = await res.json();
    document.getElementById('wizard-file-count').textContent = data.file_count || 0;
  } catch { }
}

function buildWizardSummary() {
  const first = document.getElementById('wiz-first-name').value;
  const last = document.getElementById('wiz-last-name').value;
  const name = (first + ' ' + last).trim() || t('wizard.not_set');
  const email = document.getElementById('wiz-email').value || t('wizard.not_set');
  const city = document.getElementById('wiz-city').value;
  const st = document.getElementById('wiz-state').value;
  const loc = [city, st].filter(Boolean).join(', ') || t('wizard.not_set');
  const titles = state.tagInputs['wiz-titles-tags'] || [];
  const locations = state.tagInputs['wiz-locations-tags'] || [];
  const remote = document.getElementById('wiz-remote').checked;
  const levels = [...document.querySelectorAll('.wiz-exp-level:checked')].map(c => c.value);
  const hasResume = !!state.wizardData.resume_file;

  document.getElementById('wizard-summary').innerHTML = `
    <div><strong>${t('wizard.summary_name')}</strong> ${escHtml(name)}</div>
    <div><strong>${t('wizard.summary_email')}</strong> ${escHtml(email)}</div>
    <div><strong>${t('wizard.summary_location')}</strong> ${escHtml(loc)}</div>
    <div><strong>${t('wizard.summary_titles')}</strong> ${titles.length ? escHtml(titles.join(', ')) : t('wizard.none')}</div>
    <div><strong>${t('wizard.summary_locations')}</strong> ${locations.length ? escHtml(locations.join(', ')) : t('wizard.none')}</div>
    <div><strong>${t('wizard.summary_remote')}</strong> ${remote ? t('wizard.yes') : t('wizard.no')}</div>
    <div><strong>${t('wizard.summary_experience')}</strong> ${levels.length ? levels.join(', ') : t('wizard.none')}</div>
    <div><strong>${t('wizard.summary_resume')}</strong> ${hasResume ? t('wizard.uploaded') : t('wizard.skipped')}</div>
  `;
}

function _collectWizardScreeningAnswers() {
  const ans = {};
  const fields = {
    'wiz-work-authorization': 'work_authorization',
    'wiz-visa-sponsorship':   'visa_sponsorship',
    'wiz-years-experience':   'years_experience',
    'wiz-desired-salary':     'desired_salary',
    'wiz-willing-relocate':   'willing_to_relocate',
    'wiz-start-date':         'start_date',
  };
  for (const [id, key] of Object.entries(fields)) {
    const el = document.getElementById(id);
    if (el && el.value) ans[key] = el.value;
  }
  return ans;
}

export async function wizardFinish() {
  const config = {
    profile: {
      first_name:         document.getElementById('wiz-first-name').value,
      last_name:          document.getElementById('wiz-last-name').value,
      email:              document.getElementById('wiz-email').value,
      phone_country_code: document.getElementById('wiz-phone-code').value || '+1',
      phone:              document.getElementById('wiz-phone').value,
      address_line1:      document.getElementById('wiz-address1').value,
      address_line2:      document.getElementById('wiz-address2').value,
      city:               document.getElementById('wiz-city').value,
      state:              document.getElementById('wiz-state').value,
      zip_code:           document.getElementById('wiz-zip').value,
      country:            document.getElementById('wiz-country').value || 'United States',
      bio:                document.getElementById('wiz-bio').value,
      linkedin_url:       document.getElementById('wiz-linkedin').value,
      portfolio_url:      document.getElementById('wiz-portfolio').value,
      screening_answers:  _collectWizardScreeningAnswers(),
    },
    search_criteria: {
      job_titles:        state.tagInputs['wiz-titles-tags'] || [],
      locations:         state.tagInputs['wiz-locations-tags'] || [],
      remote_only:       document.getElementById('wiz-remote').checked,
      salary_min:        parseInt(document.getElementById('wiz-salary').value) || null,
      keywords_include:  state.tagInputs['wiz-include-tags'] || [],
      keywords_exclude:  state.tagInputs['wiz-exclude-tags'] || [],
      experience_levels: [...document.querySelectorAll('.wiz-exp-level:checked')].map(c => c.value),
    },
  };

  try {
    await fetch('/api/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });
  } catch (e) {
    console.warn('Could not save config:', e);
  }

  // Upload resume if present
  if (state.wizardData.resume_file) {
    try {
      const fd = new FormData();
      fd.append('file', state.wizardData.resume_file);
      await fetch('/api/profile/resume', { method: 'POST', body: fd });
    } catch (e) {
      console.warn('Could not upload resume:', e);
    }
  }

  showApp();
}
