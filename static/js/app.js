/* ═══════════════════════════════════════════════════════════════
   APP — Entry Point
   ═══════════════════════════════════════════════════════════════ */

// Auth must run first (patches window.fetch)
import './auth.js';

import { t, getLocale, setLocale, onReady } from './i18n.js';
import { state } from './state.js';
import { initSocket } from './socket.js';
import { initTagInputs, addTag, addTagFromInput, removeTag } from './tag-input.js';
import { initFileUpload } from './file-upload.js';
import { initNavTabs, showApp, switchScreen } from './navigation.js';
import { showWizard, setWizardStep, wizardNext, wizardPrev, wizardFinish, wizardRefreshFiles } from './wizard.js';
import { botControl } from './bot-control.js';
import { clearFeed } from './feed.js';
import { debounceSearch, loadApplications, goAppPage, updateAppStatus, updateAppNotes, viewCoverLetter, viewApplicationDetail, updateDetailStatus, saveDetailNotes, exportCSV } from './applications.js';
import { loadProfileFiles, showFileModal, editFile, saveFile, confirmDeleteFile } from './profile.js';
import { loadSettings, saveSettings, updateScheduleUI, changeApplyMode, onLLMProviderChange, validateLLMKey, onLocaleChange } from './settings.js';
import { reviewApprove, reviewEdit, reviewManualSubmit, reviewSkip } from './review.js';
import { openLoginBrowser, closeLoginBrowser } from './login.js';
import { closeModal } from './modals.js';
import { updateAIIndicators } from './ai-status.js';
import { switchAnalyticsPeriod } from './analytics.js';
import { loadResumes, viewResume, closeResumeDetail, previewResumePdf, downloadResume, switchResumePage, initResumeSearch, toggleFavorite, compareSelected, closeCompareView, onCompareCheck } from './resumes.js';
import { loadKnowledgeBase, loadKBEntries, uploadKBDocument, editKBEntry, saveKBEntry, closeKBEdit, deleteKBEntry, filterKBCategory, searchKB, switchKBPage, loadKBDocuments, initKnowledgeBase, analyzeATS } from './knowledge-base.js';
import { previewKBResume, closeKBPreview, initResumePreview } from './resume-preview.js';
import { initResumeBuilder, openResumeBuilder, closeResumeBuilder, addToResume, removeFromResume, moveEntryUp, moveEntryDown, savePreset, loadPreset, deletePreset, previewBuilderResume, autoFillFromJD } from './resume-builder.js';

// ── Expose globals for inline onclick handlers in HTML ──────────
// These are used by onclick attributes in the HTML template.
// As modules have their own scope, we must attach them to window.
window.setWizardStep = setWizardStep;
window.wizardNext = wizardNext;
window.wizardPrev = wizardPrev;
window.wizardFinish = wizardFinish;
window.wizardRefreshFiles = wizardRefreshFiles;
window.openLoginBrowser = openLoginBrowser;
window.closeLoginBrowser = closeLoginBrowser;
window.botControl = botControl;
window.clearFeed = clearFeed;
window.addTag = addTag;
window.addTagFromInput = addTagFromInput;
window.removeTag = removeTag;
window.debounceSearch = debounceSearch;
window.loadApplications = loadApplications;
window.goAppPage = goAppPage;
window.updateAppStatus = updateAppStatus;
window.updateAppNotes = updateAppNotes;
window.viewCoverLetter = viewCoverLetter;
window.viewApplicationDetail = viewApplicationDetail;
window.updateDetailStatus = updateDetailStatus;
window.saveDetailNotes = saveDetailNotes;
window.exportCSV = exportCSV;
window.showFileModal = showFileModal;
window.editFile = editFile;
window.saveFile = saveFile;
window.confirmDeleteFile = confirmDeleteFile;
window.saveSettings = saveSettings;
window.updateScheduleUI = updateScheduleUI;
window.changeApplyMode = changeApplyMode;
window.onLLMProviderChange = onLLMProviderChange;
window.validateLLMKey = validateLLMKey;
window.onLocaleChange = onLocaleChange;
window.reviewApprove = reviewApprove;
window.reviewEdit = reviewEdit;
window.reviewManualSubmit = reviewManualSubmit;
window.reviewSkip = reviewSkip;
window.closeModal = closeModal;
window.switchAnalyticsPeriod = switchAnalyticsPeriod;
window.viewResume = viewResume;
window.closeResumeDetail = closeResumeDetail;
window.previewResumePdf = previewResumePdf;
window.downloadResume = downloadResume;
window.switchResumePage = switchResumePage;
window.toggleFavorite = toggleFavorite;
window.compareSelected = compareSelected;
window.closeCompareView = closeCompareView;
window.onCompareCheck = onCompareCheck;
window.switchScreen = switchScreen;
window.showScreen = switchScreen;
window.uploadKBDocument = uploadKBDocument;
window.editKBEntry = editKBEntry;
window.saveKBEntry = saveKBEntry;
window.closeKBEdit = closeKBEdit;
window.deleteKBEntry = deleteKBEntry;
window.filterKBCategory = filterKBCategory;
window.searchKB = searchKB;
window.switchKBPage = switchKBPage;
window.analyzeATS = analyzeATS;
window.previewKBResume = previewKBResume;
window.closeKBPreview = closeKBPreview;
window.openResumeBuilder = openResumeBuilder;
window.closeResumeBuilder = closeResumeBuilder;
window.addToResume = addToResume;
window.removeFromResume = removeFromResume;
window.moveEntryUp = moveEntryUp;
window.moveEntryDown = moveEntryDown;
window.savePreset = savePreset;
window.loadPreset = loadPreset;
window.deletePreset = deletePreset;
window.previewBuilderResume = previewBuilderResume;
window.autoFillFromJD = autoFillFromJD;
window.t = t;
window.getLocale = getLocale;
window.setLocale = setLocale;

/* ═══════════════════════════════════════════════════════════════
   ACCESSIBILITY — Event delegation for keyboard support
   ═══════════════════════════════════════════════════════════════ */
function initAccessibility() {
  // Clickable table rows: Enter/Space opens detail view
  document.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') {
      const row = e.target.closest('tr.clickable-row');
      if (row && !e.target.closest('.no-row-click')) {
        e.preventDefault();
        const id = row.dataset.appId;
        if (id) viewApplicationDetail(id);
      }
    }
  });

  // Event delegation for dynamically rendered buttons (cover letter, status, notes, pagination)
  document.addEventListener('click', e => {
    // Cover letter view in table
    const coverBtn = e.target.closest('[data-cover-id]');
    if (coverBtn) { viewCoverLetter(coverBtn.dataset.coverId); return; }

    // Pagination
    const pageBtn = e.target.closest('[data-page]');
    if (pageBtn && !pageBtn.disabled) { goAppPage(parseInt(pageBtn.dataset.page, 10)); return; }

    // Clickable row
    const row = e.target.closest('tr.clickable-row');
    if (row && !e.target.closest('.no-row-click')) {
      viewApplicationDetail(row.dataset.appId);
      return;
    }

    // Detail modal: save notes
    const saveNotesBtn = e.target.closest('[data-save-notes-id]');
    if (saveNotesBtn) { saveDetailNotes(saveNotesBtn.dataset.saveNotesId); return; }

    // Detail modal: cover letter
    const detailCoverBtn = e.target.closest('[data-detail-cover-id]');
    if (detailCoverBtn) { viewCoverLetter(detailCoverBtn.dataset.detailCoverId); return; }

    // Profile: edit file
    const editBtn = e.target.closest('[data-edit-file]');
    if (editBtn) { editFile(editBtn.dataset.editFile); return; }

    // Profile: delete file
    const deleteBtn = e.target.closest('[data-delete-file]');
    if (deleteBtn) { confirmDeleteFile(deleteBtn.dataset.deleteFile); return; }
  });

  // Status change via event delegation
  document.addEventListener('change', e => {
    const statusSelect = e.target.closest('[data-status-id]');
    if (statusSelect) { updateAppStatus(statusSelect.dataset.statusId, statusSelect.value); return; }

    const detailStatusSelect = e.target.closest('[data-detail-status-id]');
    if (detailStatusSelect) { updateDetailStatus(detailStatusSelect.dataset.detailStatusId); return; }
  });

  // Notes blur save via event delegation
  document.addEventListener('blur', e => {
    const notesInput = e.target.closest('[data-notes-id]');
    if (notesInput) { updateAppNotes(notesInput.dataset.notesId, notesInput.value); }
  }, true);
}

/* ═══════════════════════════════════════════════════════════════
   INITIALIZATION
   ═══════════════════════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', async () => {
  initTagInputs();
  initNavTabs();
  initFileUpload();
  initSocket();
  initAccessibility();
  initResumeSearch();
  initKnowledgeBase();
  initResumePreview();
  initResumeBuilder();

  try {
    const res = await fetch('/api/setup/status');
    const data = await res.json();
    state.aiAvailable = !!data.ai_available;
    updateAIIndicators();
    const banner = document.getElementById('ai-warning-banner');
    if (banner) banner.classList.toggle('hidden', state.aiAvailable);

    if (data.is_first_run) {
      showWizard(data);
    } else {
      showApp();
    }
  } catch (e) {
    console.warn('Could not reach setup API, showing app:', e);
    showApp();
  }
});
