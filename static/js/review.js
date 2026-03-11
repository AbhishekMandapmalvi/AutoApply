/* ═══════════════════════════════════════════════════════════════
   REVIEW CARD
   ═══════════════════════════════════════════════════════════════ */
import { t } from './i18n.js';

export function showReviewCard(evt) {
  const card = document.getElementById('review-card');
  document.getElementById('review-job-title').textContent =
    (evt.job_title || t('review.unknown')) + ' ' + t('review.at') + ' ' + (evt.company || t('review.unknown'));
  document.getElementById('review-platform').textContent = evt.platform || '';
  document.getElementById('review-score').textContent = evt.match_score || '--';
  document.getElementById('review-cover-letter').value = evt.cover_letter || '';
  // Store apply URL for manual submit
  card.dataset.applyUrl = evt.apply_url || '';
  const manualBtn = document.getElementById('review-manual-submit');
  if (manualBtn) manualBtn.classList.toggle('hidden', !evt.apply_url);
  card.classList.remove('hidden');
  card.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

export function hideReviewCard() {
  document.getElementById('review-card').classList.add('hidden');
}

export async function reviewApprove() {
  try {
    await fetch('/api/bot/review/approve', { method: 'POST' });
    hideReviewCard();
  } catch (e) {
    console.warn('Review approve error:', e);
  }
}

export async function reviewEdit() {
  const coverLetter = document.getElementById('review-cover-letter').value;
  try {
    await fetch('/api/bot/review/edit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cover_letter: coverLetter }),
    });
    hideReviewCard();
  } catch (e) {
    console.warn('Review edit error:', e);
  }
}

export async function reviewManualSubmit() {
  // Open the job URL so the user can apply themselves
  const card = document.getElementById('review-card');
  const url = card.dataset.applyUrl;
  if (url) window.open(url, '_blank');
  // Tell the bot to save this as manual_required and move on
  try {
    await fetch('/api/bot/review/manual', { method: 'POST' });
    hideReviewCard();
  } catch (e) {
    console.warn('Review manual error:', e);
  }
}

export async function reviewSkip() {
  try {
    await fetch('/api/bot/review/skip', { method: 'POST' });
    hideReviewCard();
  } catch (e) {
    console.warn('Review skip error:', e);
  }
}
