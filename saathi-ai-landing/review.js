/**
 * Saathi AI — Complaint Review, Editing, and Confirmation Client
 * Phase 5 Implementation
 */

document.addEventListener('DOMContentLoaded', () => {
  // -------------------------------------------------------------------------
  // 1. Token & API Endpoint Extraction
  // -------------------------------------------------------------------------
  function getTokenFromLocation() {
    const pathParts = window.location.pathname.split('/').filter(Boolean);
    // Expected path: /c/{token}
    if (pathParts.length >= 2 && pathParts[0] === 'c') {
      return decodeURIComponent(pathParts[1]);
    }
    // Fallback: check query parameter ?token=...
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('token') || '';
  }

  function getApiBaseUrl() {
    const origin = window.location.origin;
    if (origin.includes(':8000') || !window.location.port) {
      return '';
    }
    const hostname = window.location.hostname || 'localhost';
    const protocol = window.location.protocol || 'http:';
    return `${protocol}//${hostname}:8000`;
  }

  const API_BASE = getApiBaseUrl();
  const COMPLAINT_TOKEN = getTokenFromLocation();

  // DOM Elements - State Cards
  const cardProcessing = document.getElementById('card-processing');
  const cardFailed = document.getElementById('card-failed');
  const cardCancelled = document.getElementById('card-cancelled');
  const bannerConfirmed = document.getElementById('banner-confirmed');
  const reviewContent = document.getElementById('review-content');

  // DOM Elements - Header & Meta Bar
  const displayRefNumber = document.getElementById('display-ref-number');
  const displayStatusPill = document.getElementById('display-status-pill');
  const displayTimestamp = document.getElementById('display-timestamp');
  const globalAlertBanner = document.getElementById('global-alert-banner');
  const globalAlertMsg = document.getElementById('global-alert-msg');
  const globalAlertIcon = document.getElementById('global-alert-icon');
  const btnCloseAlert = document.getElementById('btn-close-alert');

  // DOM Elements - Processing Steps
  const pstepUpload = document.getElementById('pstep-upload');
  const pstepTranscribe = document.getElementById('pstep-transcribe');
  const pstepExtract = document.getElementById('pstep-extract');
  const failedErrorMsg = document.getElementById('failed-error-msg');
  const cancelledRef = document.getElementById('cancelled-ref');
  const cancelledTimestamp = document.getElementById('cancelled-timestamp');

  // DOM Elements - Sections A, B, C
  const displayEnglishSummary = document.getElementById('display-english-summary');
  const displayOriginalTranscript = document.getElementById('display-original-transcript');
  const detectedLangName = document.getElementById('detected-lang-name');
  const summaryTranslationBadge = document.getElementById('summary-translation-badge');

  // Form & Inputs
  const complaintForm = document.getElementById('complaint-edit-form');
  const btnToggleEdit = document.getElementById('btn-toggle-edit');
  const btnSaveDraft = document.getElementById('btn-save-draft');
  const btnCancelEdit = document.getElementById('btn-cancel-edit');
  const editSaveBar = document.getElementById('edit-save-bar');
  const saveStatusMsg = document.getElementById('save-status-msg');

  // Form Fields
  const fieldIncidentType = document.getElementById('field-incident-type');
  const fieldSummary = document.getElementById('field-summary');
  const fieldDescription = document.getElementById('field-description');
  const fieldReportedEntity = document.getElementById('field-reported-entity');
  const fieldIncidentDate = document.getElementById('field-incident-date');
  const fieldFinancialLoss = document.getElementById('field-financial-loss');
  const fieldCurrency = document.getElementById('field-currency');
  const fieldPhoneNumber = document.getElementById('field-phone-number');
  const fieldSuspectedScam = document.getElementById('field-suspected-scam');
  const fieldEvidenceDescription = document.getElementById('field-evidence-description');

  // Missing Badges
  const missingBadges = {
    incident_type: document.getElementById('badge-incident-type'),
    summary: document.getElementById('badge-summary'),
    description: document.getElementById('badge-description'),
    reported_entity: document.getElementById('badge-reported-entity'),
    incident_date: document.getElementById('badge-incident-date'),
    financial_loss: document.getElementById('badge-financial-loss'),
    currency: document.getElementById('badge-currency'),
    phone_number: document.getElementById('badge-phone-number'),
    suspected_scam: document.getElementById('badge-suspected-scam'),
    evidence_description: document.getElementById('badge-evidence-description'),
  };

  // Sidebar Actions
  const missingCountBadge = document.getElementById('missing-count-badge');
  const btnConfirmPrimary = document.getElementById('btn-confirm-primary');
  const btnEditPrimary = document.getElementById('btn-edit-primary');
  const btnCancelPrimary = document.getElementById('btn-cancel-primary');

  // Modal Cancel Elements
  const modalCancel = document.getElementById('modal-cancel');
  const btnDismissModal = document.getElementById('btn-dismiss-modal');
  const btnConfirmCancelDialog = document.getElementById('btn-confirm-cancel-dialog');
  const cancelReasonInput = document.getElementById('cancel-reason-input');

  // Phase 6 Relief Actions DOM Elements
  const confirmedRefBadge = document.getElementById('confirmed-ref-badge');
  const btnActionNotifyBank = document.getElementById('btn-action-notify-bank');
  const btnActionCall1930 = document.getElementById('btn-action-call-1930');
  const btnActionDownloadPdf = document.getElementById('btn-action-download-pdf');
  const btnActionViewPortalGuide = document.getElementById('btn-action-view-portal-guide');
  const btnActionFirSimulation = document.getElementById('btn-action-fir-simulation');
  const btnActionTrackStatus = document.getElementById('btn-action-track-status');

  // Phase 6 Modals
  const modalBankEmail = document.getElementById('modal-bank-email');
  const btnCloseBankModal = document.getElementById('btn-close-bank-modal');
  const btnLaunchEmailClient = document.getElementById('btn-launch-email-client');
  const bankEmailRecipient = document.getElementById('bank-email-recipient');
  const bankEmailSubjectPreview = document.getElementById('bank-email-subject-preview');
  const bankEmailBodyPreview = document.getElementById('bank-email-body-preview');

  const modalCall1930 = document.getElementById('modal-call-1930');
  const btnCloseCallModal = document.getElementById('btn-close-call-modal');
  const btnProceedCall1930 = document.getElementById('btn-proceed-call-1930');

  const modalPortalGuide = document.getElementById('modal-portal-guide');
  const btnClosePortalModal = document.getElementById('btn-close-portal-modal');
  const guideRefCode = document.getElementById('guide-ref-code');
  const portalCopyTextarea = document.getElementById('portal-copy-textarea');
  const btnCopyPortalText = document.getElementById('btn-copy-portal-text');
  const portalCopyFeedback = document.getElementById('portal-copy-feedback');

  const modalFirSimulation = document.getElementById('modal-fir-simulation');
  const btnCloseSimModal = document.getElementById('btn-close-sim-modal');
  const btnRunFirSimulation = document.getElementById('btn-run-fir-simulation');
  const simTimelineBox = document.getElementById('sim-timeline-box');

  // Internal State
  let currentComplaint = null;
  let isEditMode = false;
  let pollingInterval = null;
  let originalFormValues = {};

  // -------------------------------------------------------------------------
  // 2. Alert Notification Helper
  // -------------------------------------------------------------------------
  function showAlert(message, type = 'info') {
    if (!globalAlertBanner) return;
    globalAlertMsg.textContent = message;
    globalAlertBanner.className = `alert-banner ${type}`;
    if (type === 'success') globalAlertIcon.textContent = '✅';
    else if (type === 'error') globalAlertIcon.textContent = '⚠️';
    else globalAlertIcon.textContent = 'ℹ️';
    globalAlertBanner.style.display = 'flex';
  }

  if (btnCloseAlert) {
    btnCloseAlert.addEventListener('click', () => {
      globalAlertBanner.style.display = 'none';
    });
  }

  // -------------------------------------------------------------------------
  // 3. State Management: Switching Between the 5 Lifecycle States
  // -------------------------------------------------------------------------
  function setViewState(stateName, data = {}) {
    // Hide all main cards first
    cardProcessing.style.display = 'none';
    cardFailed.style.display = 'none';
    cardCancelled.style.display = 'none';
    reviewContent.style.display = 'none';

    if (stateName === 'processing') {
      cardProcessing.style.display = 'block';
      displayStatusPill.textContent = 'Processing';
      displayStatusPill.className = 'status-pill status-processing';

      const procStatus = data.processing_status || 'transcribing';
      if (procStatus === 'received') {
        pstepUpload.className = 'proc-step active';
        pstepTranscribe.className = 'proc-step';
        pstepExtract.className = 'proc-step';
      } else if (procStatus === 'transcribing') {
        pstepUpload.className = 'proc-step active';
        pstepTranscribe.className = 'proc-step active';
        pstepExtract.className = 'proc-step';
      } else if (procStatus === 'extracting') {
        pstepUpload.className = 'proc-step active';
        pstepTranscribe.className = 'proc-step active';
        pstepExtract.className = 'proc-step active';
      }
    } else if (stateName === 'failed') {
      stopPolling();
      cardFailed.style.display = 'block';
      displayStatusPill.textContent = 'Failed';
      displayStatusPill.className = 'status-pill status-cancelled';
      if (data.error_message && failedErrorMsg) {
        failedErrorMsg.textContent = data.error_message;
      }
    } else if (stateName === 'cancelled') {
      stopPolling();
      cardCancelled.style.display = 'block';
      bannerConfirmed.style.display = 'none';
      displayStatusPill.textContent = 'Cancelled';
      displayStatusPill.className = 'status-pill status-cancelled';
      if (cancelledRef) cancelledRef.textContent = data.reference_number || 'N/A';
      if (cancelledTimestamp) {
        cancelledTimestamp.textContent = data.cancelled_at ? new Date(data.cancelled_at).toLocaleString() : 'Just now';
      }
      disableAllActions();
    } else if (stateName === 'confirmed') {
      stopPolling();
      reviewContent.style.display = 'grid';
      bannerConfirmed.style.display = 'block';
      displayStatusPill.textContent = 'Confirmed';
      displayStatusPill.className = 'status-pill status-confirmed';
      if (confirmedRefBadge) {
        confirmedRefBadge.textContent = data.reference_number || (currentComplaint ? currentComplaint.reference_number : 'SAI-XXXXXX');
      }
      setEditMode(false);
      btnEditPrimary.disabled = true;
      btnCancelPrimary.disabled = true;
      btnConfirmPrimary.disabled = true;
      btnToggleEdit.style.display = 'none';
    } else if (stateName === 'awaiting_review') {
      stopPolling();
      reviewContent.style.display = 'grid';
      bannerConfirmed.style.display = 'none';
      displayStatusPill.textContent = 'Ready for Review';
      displayStatusPill.className = 'status-pill status-awaiting';
      btnEditPrimary.disabled = false;
      btnCancelPrimary.disabled = false;
      btnConfirmPrimary.disabled = false;
    }
  }

  function disableAllActions() {
    btnConfirmPrimary.disabled = true;
    btnEditPrimary.disabled = true;
    btnCancelPrimary.disabled = true;
    btnToggleEdit.disabled = true;
    if (btnActionNotifyBank) btnActionNotifyBank.disabled = true;
    if (btnActionCall1930) btnActionCall1930.disabled = true;
    if (btnActionDownloadPdf) btnActionDownloadPdf.disabled = true;
    if (btnActionViewPortalGuide) btnActionViewPortalGuide.disabled = true;
    if (btnActionFirSimulation) btnActionFirSimulation.disabled = true;
    if (btnActionTrackStatus) btnActionTrackStatus.disabled = true;
  }

  // -------------------------------------------------------------------------
  // 4. Data Population for Sections A, B, and C
  // -------------------------------------------------------------------------
  function renderComplaintData(data) {
    currentComplaint = data;

    // Header Reference & Timestamps
    if (displayRefNumber) {
      displayRefNumber.textContent = data.reference_number || 'PENDING ASSIGNMENT';
    }
    if (confirmedRefBadge && data.reference_number) {
      confirmedRefBadge.textContent = data.reference_number;
    }
    if (displayTimestamp && data.created_at) {
      const dt = new Date(data.created_at);
      displayTimestamp.textContent = `Filed: ${dt.toLocaleDateString()} ${dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
    }

    // SECTION A: Complaint Summary in English
    if (displayEnglishSummary) {
      let eng = data.english_summary;
      if (typeof eng === 'object' && eng !== null) {
        eng = eng.english_translation || eng.translation || JSON.stringify(eng);
      }
      displayEnglishSummary.textContent = eng || data.structured_fields?.summary || 'Summary unavailable.';
    }
    if (summaryTranslationBadge) {
      const isOriginalEnglish = (data.language === 'en');
      summaryTranslationBadge.textContent = isOriginalEnglish ? '🇺🇸 Original English' : '🌐 AI-Translated English Summary';
    }

    // SECTION B: Original Voice Transcript
    if (displayOriginalTranscript) {
      displayOriginalTranscript.textContent = data.original_transcript || 'Audio transcript is not available.';
    }
    if (detectedLangName) {
      detectedLangName.textContent = data.language_name || (data.language ? data.language.toUpperCase() : 'Unknown');
    }

    // SECTION C: Structured Complaint Fields
    const fields = data.structured_fields || {};
    populateFormFields(fields);

    // Missing Field Badges
    const missing = data.missing_fields || [];
    updateMissingBadges(missing);

    // Prepare Option 1 1-Click Auto-Filler Payload
    setupAutofillModal();
  }

  function populateFormFields(fields) {
    fieldIncidentType.value = fields.incident_type || '';
    fieldSummary.value = fields.summary || '';
    fieldDescription.value = fields.description || '';
    fieldReportedEntity.value = fields.reported_entity || '';
    fieldIncidentDate.value = fields.incident_date || '';
    fieldFinancialLoss.value = (fields.financial_loss != null) ? fields.financial_loss : '';
    fieldCurrency.value = fields.currency || 'INR';
    fieldPhoneNumber.value = fields.phone_number || '';

    if (fields.suspected_scam === true) {
      fieldSuspectedScam.value = 'true';
    } else if (fields.suspected_scam === false) {
      fieldSuspectedScam.value = 'false';
    } else {
      fieldSuspectedScam.value = '';
    }

    fieldEvidenceDescription.value = fields.evidence_description || '';

    // Snapshot original values for cancel editing
    originalFormValues = {
      incident_type: fieldIncidentType.value,
      summary: fieldSummary.value,
      description: fieldDescription.value,
      reported_entity: fieldReportedEntity.value,
      incident_date: fieldIncidentDate.value,
      financial_loss: fieldFinancialLoss.value,
      currency: fieldCurrency.value,
      phone_number: fieldPhoneNumber.value,
      suspected_scam: fieldSuspectedScam.value,
      evidence_description: fieldEvidenceDescription.value,
    };
  }

  function updateMissingBadges(missingList) {
    let missingCount = 0;
    const missingSet = new Set(missingList);

    for (const [key, badgeEl] of Object.entries(missingBadges)) {
      if (!badgeEl) continue;
      if (missingSet.has(key)) {
        badgeEl.style.display = 'inline-block';
        missingCount++;
      } else {
        badgeEl.style.display = 'none';
      }
    }

    if (missingCountBadge) {
      missingCountBadge.textContent = missingCount;
    }
  }

  // -------------------------------------------------------------------------
  // 5. Polling Lifecycle Endpoint
  // -------------------------------------------------------------------------
  async function fetchComplaintStatus() {
    if (!COMPLAINT_TOKEN) {
      showAlert('No complaint token found in URL path. Please verify the link.', 'error');
      setViewState('failed', { error_message: 'Missing complaint token in address.' });
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/api/complaints/${encodeURIComponent(COMPLAINT_TOKEN)}`);

      if (!response.ok) {
        if (response.status === 404) {
          showAlert('Complaint not found or token has expired.', 'error');
          setViewState('failed', { error_message: 'Complaint record not found for this token.' });
          return;
        }
        if (response.status === 401) {
          showAlert('Complaint access token has expired.', 'error');
          setViewState('failed', { error_message: 'The secure link for this complaint has expired.' });
          return;
        }
        throw new Error(`Server returned status ${response.status}`);
      }

      const data = await response.json();
      const complaintStatus = (data.status || '').toLowerCase();
      const processingStatus = (data.processing_status || '').toLowerCase();

      // Check current state
      if (complaintStatus === 'failed' || processingStatus === 'failed') {
        setViewState('failed', data);
      } else if (complaintStatus === 'cancelled') {
        renderComplaintData(data);
        setViewState('cancelled', data);
      } else if (complaintStatus === 'confirmed') {
        renderComplaintData(data);
        setViewState('confirmed', data);
      } else if (complaintStatus === 'awaiting_review' || complaintStatus === 'pending_review' || processingStatus === 'completed') {
        renderComplaintData(data);
        setViewState('awaiting_review', data);
      } else {
        // Still processing
        setViewState('processing', data);
      }
    } catch (err) {
      console.warn('Error querying complaint status:', err);
    }
  }

  function startPolling() {
    fetchComplaintStatus();
    pollingInterval = setInterval(fetchComplaintStatus, 2500);
  }

  function stopPolling() {
    if (pollingInterval) {
      clearInterval(pollingInterval);
      pollingInterval = null;
    }
  }

  // -------------------------------------------------------------------------
  // 6. Edit Mode & Form Handling
  // -------------------------------------------------------------------------
  function setEditMode(enabled) {
    isEditMode = enabled;
    const inputs = [
      fieldIncidentType,
      fieldSummary,
      fieldDescription,
      fieldReportedEntity,
      fieldIncidentDate,
      fieldFinancialLoss,
      fieldCurrency,
      fieldPhoneNumber,
      fieldSuspectedScam,
      fieldEvidenceDescription,
    ];

    inputs.forEach(inp => {
      if (inp) inp.disabled = !enabled;
    });

    if (editSaveBar) {
      editSaveBar.style.display = enabled ? 'flex' : 'none';
    }

    if (btnToggleEdit) {
      btnToggleEdit.textContent = enabled ? '✕ Cancel Edit' : '✏️ Edit Fields';
    }

    if (enabled) {
      fieldSummary.focus();
    }
  }

  if (btnToggleEdit) {
    btnToggleEdit.addEventListener('click', () => {
      setEditMode(!isEditMode);
    });
  }

  if (btnEditPrimary) {
    btnEditPrimary.addEventListener('click', () => {
      setEditMode(true);
      fieldSummary.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  }

  if (btnCancelEdit) {
    btnCancelEdit.addEventListener('click', () => {
      // Revert to original snapshot
      populateFormFields(originalFormValues);
      setEditMode(false);
    });
  }

  // Save Edits via PATCH /api/complaints/{token}
  async function saveFormEdits() {
    if (!COMPLAINT_TOKEN) return;

    // Basic client validation
    if (!fieldSummary.value.trim() || fieldSummary.value.trim().length < 3) {
      showAlert('Summary must be at least 3 characters long.', 'error');
      fieldSummary.focus();
      return;
    }
    if (!fieldDescription.value.trim() || fieldDescription.value.trim().length < 5) {
      showAlert('Description must be at least 5 characters long.', 'error');
      fieldDescription.focus();
      return;
    }

    btnSaveDraft.disabled = true;
    saveStatusMsg.textContent = 'Saving...';
    saveStatusMsg.style.color = 'var(--text-secondary)';

    const lossVal = fieldFinancialLoss.value.trim();
    const scamVal = fieldSuspectedScam.value;

    const payload = {
      incident_type: fieldIncidentType.value || null,
      summary: fieldSummary.value.trim(),
      description: fieldDescription.value.trim(),
      reported_entity: fieldReportedEntity.value.trim() || null,
      incident_date: fieldIncidentDate.value.trim() || null,
      financial_loss: lossVal ? parseFloat(lossVal) : null,
      currency: fieldCurrency.value || 'INR',
      phone_number: fieldPhoneNumber.value.trim() || null,
      suspected_scam: scamVal === 'true' ? true : (scamVal === 'false' ? false : null),
      evidence_description: fieldEvidenceDescription.value.trim() || null,
    };

    try {
      const resp = await fetch(`${API_BASE}/api/complaints/${encodeURIComponent(COMPLAINT_TOKEN)}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to save complaint edits.');
      }

      const updated = await resp.json();
      renderComplaintData(updated);
      setEditMode(false);
      showAlert('Edits saved successfully. Sensitive credentials sanitized.', 'success');
    } catch (err) {
      showAlert(err.message, 'error');
      saveStatusMsg.textContent = 'Save failed.';
      saveStatusMsg.style.color = 'var(--color-danger)';
    } finally {
      btnSaveDraft.disabled = false;
    }
  }

  if (btnSaveDraft) {
    btnSaveDraft.addEventListener('click', saveFormEdits);
  }

  // -------------------------------------------------------------------------
  // 7. Confirmation Workflow (POST /api/complaints/{token}/confirm)
  // -------------------------------------------------------------------------
  async function confirmComplaint() {
    if (!COMPLAINT_TOKEN) return;

    if (!confirm('Are you sure you want to finalize and confirm this complaint?\n\nThis will lock the verified facts and generate your formal dispute documentation.')) {
      return;
    }

    btnConfirmPrimary.disabled = true;
    btnConfirmPrimary.innerHTML = '<span>⏳</span> Confirming...';

    // Collect any unsaved edits currently in form
    const lossVal = fieldFinancialLoss.value.trim();
    const scamVal = fieldSuspectedScam.value;

    const payload = {
      notes: 'Complaint verified and confirmed by victim.',
      incident_type: fieldIncidentType.value || null,
      summary: fieldSummary.value.trim(),
      description: fieldDescription.value.trim(),
      reported_entity: fieldReportedEntity.value.trim() || null,
      incident_date: fieldIncidentDate.value.trim() || null,
      financial_loss: lossVal ? parseFloat(lossVal) : null,
      currency: fieldCurrency.value || 'INR',
      phone_number: fieldPhoneNumber.value.trim() || null,
      suspected_scam: scamVal === 'true' ? true : (scamVal === 'false' ? false : null),
      evidence_description: fieldEvidenceDescription.value.trim() || null,
    };

    try {
      const resp = await fetch(`${API_BASE}/api/complaints/${encodeURIComponent(COMPLAINT_TOKEN)}/confirm`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to confirm complaint.');
      }

      const confirmedData = await resp.json();
      showAlert('Complaint verified and confirmed successfully!', 'success');

      // Refresh full details
      await fetchComplaintStatus();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (err) {
      showAlert(err.message, 'error');
      btnConfirmPrimary.disabled = false;
      btnConfirmPrimary.innerHTML = `
        <span class="btn-icon">✅</span>
        <div class="btn-text-block">
          <strong>Confirm Complaint</strong>
          <small>Lock verified facts & unlock reporting</small>
        </div>
      `;
    }
  }

  if (btnConfirmPrimary) {
    btnConfirmPrimary.addEventListener('click', confirmComplaint);
  }

  // -------------------------------------------------------------------------
  // 8. Cancellation Workflow (POST /api/complaints/{token}/cancel)
  // -------------------------------------------------------------------------
  if (btnCancelPrimary) {
    btnCancelPrimary.addEventListener('click', () => {
      if (modalCancel) {
        modalCancel.style.display = 'flex';
        if (cancelReasonInput) cancelReasonInput.value = '';
      }
    });
  }

  if (btnDismissModal) {
    btnDismissModal.addEventListener('click', () => {
      if (modalCancel) modalCancel.style.display = 'none';
    });
  }

  if (btnConfirmCancelDialog) {
    btnConfirmCancelDialog.addEventListener('click', async () => {
      if (!COMPLAINT_TOKEN) return;

      const reason = cancelReasonInput ? cancelReasonInput.value.trim() : '';
      btnConfirmCancelDialog.disabled = true;
      btnConfirmCancelDialog.textContent = 'Cancelling...';

      try {
        const resp = await fetch(`${API_BASE}/api/complaints/${encodeURIComponent(COMPLAINT_TOKEN)}/cancel`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ reason: reason || 'Cancelled by user.' }),
        });

        if (!resp.ok) {
          const errData = await resp.json().catch(() => ({}));
          throw new Error(errData.detail || 'Failed to cancel complaint.');
        }

        const data = await resp.json();
        if (modalCancel) modalCancel.style.display = 'none';
        showAlert('Complaint has been cancelled.', 'info');
        setViewState('cancelled', data);
      } catch (err) {
        showAlert(err.message, 'error');
      } finally {
        btnConfirmCancelDialog.disabled = false;
        btnConfirmCancelDialog.textContent = 'Yes, Cancel Complaint';
      }
    });
  }

  // -------------------------------------------------------------------------
  // 9. Phase 6: Post-Confirmation One-Tap Relief Actions & Modals
  // -------------------------------------------------------------------------
  async function recordComplaintAction(actionName, meta = {}) {
    if (!COMPLAINT_TOKEN) return null;
    try {
      const url = `${API_BASE}/api/complaints/${encodeURIComponent(COMPLAINT_TOKEN)}/actions/${encodeURIComponent(actionName)}`;
      const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ metadata: meta }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        loggerWarn(`Action ${actionName} record returned ${resp.status}: ${err.detail || 'unknown'}`);
        return null;
      }
      return await resp.json();
    } catch (e) {
      loggerWarn(`Failed to record action ${actionName}: ${e}`);
      return null;
    }
  }

  function loggerWarn(msg) {
    if (window.console && console.warn) console.warn(msg);
  }

  // -------------------------------------------------------------------------
  // Action 1: Notify My Bank
  // -------------------------------------------------------------------------
  function buildBankEmailContent() {
    if (!currentComplaint) return { subject: '', body: '' };
    const f = currentComplaint.structured_fields || {};
    const ref = currentComplaint.reference_number || 'SAI-XXXXXX';

    const incidentDate = f.incident_date || '[Add transaction date and time]';
    const incidentAmount = (f.financial_loss != null)
      ? `${f.currency || 'INR'} ${Number(f.financial_loss).toLocaleString('en-IN')}`
      : '[Add transaction amount and currency]';
    const incidentSummary = f.summary || currentComplaint.english_summary || '[Add transaction details]';

    const subject = `Urgent Fraud Report – Complaint ${ref}`;
    const body = `Dear Bank Fraud Support Team,

I am reporting a suspected fraudulent transaction and request urgent assistance.

Complaint Reference: ${ref}
Incident Date/Time: ${incidentDate}
Reported Amount: ${incidentAmount}

Incident Details:
${incidentSummary}

Please investigate this incident urgently, review the transaction, and consider placing a hold on the beneficiary account or transaction where legally and operationally permitted.

Please advise me on the steps required to secure my account, dispute the transaction, and pursue recovery of the funds where possible.

I can provide additional information through your official support channel.

Regards,
[Your Name]`;

    return { subject, body };
  }

  if (btnActionNotifyBank) {
    btnActionNotifyBank.addEventListener('click', () => {
      const { subject, body } = buildBankEmailContent();
      if (bankEmailSubjectPreview) bankEmailSubjectPreview.textContent = subject;
      if (bankEmailBodyPreview) bankEmailBodyPreview.textContent = body;
      if (modalBankEmail) modalBankEmail.style.display = 'flex';
    });
  }

  if (btnCloseBankModal && modalBankEmail) {
    btnCloseBankModal.addEventListener('click', () => {
      modalBankEmail.style.display = 'none';
    });
  }

  if (btnLaunchEmailClient) {
    btnLaunchEmailClient.addEventListener('click', async () => {
      const { subject, body } = buildBankEmailContent();
      const recipient = bankEmailRecipient ? (bankEmailRecipient.value || '').trim() : '';

      // Record backend action
      await recordComplaintAction('notify_bank', { recipient: recipient ? 'provided' : 'unspecified' });

      // Build mailto link
      const mailtoUrl = `mailto:${encodeURIComponent(recipient)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
      window.location.href = mailtoUrl;

      if (modalBankEmail) modalBankEmail.style.display = 'none';
      showAlert('Email draft prepared in your email client. Remember to tap Send.', 'info');
    });
  }

  // -------------------------------------------------------------------------
  // Action 2: Call Cybercrime Helpline (1930)
  // -------------------------------------------------------------------------
  if (btnActionCall1930) {
    btnActionCall1930.addEventListener('click', () => {
      if (modalCall1930) modalCall1930.style.display = 'flex';
    });
  }

  if (btnCloseCallModal && modalCall1930) {
    btnCloseCallModal.addEventListener('click', () => {
      modalCall1930.style.display = 'none';
    });
  }

  if (btnProceedCall1930) {
    btnProceedCall1930.addEventListener('click', async () => {
      await recordComplaintAction('call_1930');
      if (modalCall1930) modalCall1930.style.display = 'none';
      showAlert('Calling 1930 helpline initiated.', 'info');
    });
  }

  // -------------------------------------------------------------------------
  // Action 3: Download Complaint PDF
  // -------------------------------------------------------------------------
  if (btnActionDownloadPdf) {
    btnActionDownloadPdf.addEventListener('click', async () => {
      if (!COMPLAINT_TOKEN) return;
      showAlert('Preparing your official complaint PDF...', 'info');

      // The backend /api/complaints/{token}/pdf endpoint generates PDF and records download_pdf
      const pdfUrl = `${API_BASE}/api/complaints/${encodeURIComponent(COMPLAINT_TOKEN)}/pdf`;
      const a = document.createElement('a');
      a.href = pdfUrl;
      const ref = currentComplaint ? currentComplaint.reference_number : 'complaint';
      a.download = `${ref}-complaint.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);

      showAlert('Complaint PDF download initiated successfully.', 'success');
    });
  }

  // -------------------------------------------------------------------------
  // Action 4: Copy Cybercrime Portal Filing Steps
  // -------------------------------------------------------------------------
  function buildPortalFilingDetails() {
    if (!currentComplaint) return '';
    const f = currentComplaint.structured_fields || {};
    const ref = currentComplaint.reference_number || 'SAI-XXXXXX';
    const amount = (f.financial_loss != null)
      ? `${f.currency || 'INR'} ${Number(f.financial_loss).toLocaleString('en-IN')}`
      : 'Unspecified';

    return `SAATHI AI CITIZEN INCIDENT SUMMARY (Reference: cybercrime.gov.in)
======================================================================
Case Reference ID: ${ref}
Incident Category: ${f.incident_type || 'Financial Cyber Fraud'}
Incident Date: ${f.incident_date || 'Unspecified'}
Loss Amount: ${amount}
Reported Entity / Bank: ${f.reported_entity || 'Reported in statement'}
Suspect Phone / Contact: ${f.phone_number || 'Reported to authorities'}

TRANSACTION EVIDENCE & IDENTIFIERS:
${f.evidence_description || 'Transaction references provided in statement.'}

VERIFIED INCIDENT SUMMARY:
${f.summary || currentComplaint.english_summary || ''}

DETAILED FACTUAL STATEMENT:
${f.description || ''}

======================================================================
Prepared via Saathi AI for official cybercrime.gov.in citizen filing.
Protected under cybersecurity zero-credential standards (No PINs/OTPs).`;
  }

  if (btnActionViewPortalGuide) {
    btnActionViewPortalGuide.addEventListener('click', () => {
      const filingText = buildPortalFilingDetails();
      if (portalCopyTextarea) portalCopyTextarea.value = filingText;
      if (guideRefCode && currentComplaint) guideRefCode.textContent = currentComplaint.reference_number || 'SAI-XXXXXX';
      if (portalCopyFeedback) portalCopyFeedback.style.display = 'none';
      if (modalPortalGuide) modalPortalGuide.style.display = 'flex';
    });
  }

  if (btnClosePortalModal && modalPortalGuide) {
    btnClosePortalModal.addEventListener('click', () => {
      modalPortalGuide.style.display = 'none';
    });
  }

  if (btnCopyPortalText) {
    btnCopyPortalText.addEventListener('click', async () => {
      const text = portalCopyTextarea ? portalCopyTextarea.value : buildPortalFilingDetails();
      try {
        await navigator.clipboard.writeText(text);
        if (portalCopyFeedback) {
          portalCopyFeedback.style.display = 'block';
          setTimeout(() => { portalCopyFeedback.style.display = 'none'; }, 3000);
        }
        showAlert('Filing details copied to clipboard.', 'success');
      } catch {
        if (portalCopyTextarea) {
          portalCopyTextarea.select();
          document.execCommand('copy');
          if (portalCopyFeedback) portalCopyFeedback.style.display = 'block';
        }
      }
      // Record copy_filing_guide action on backend
      await recordComplaintAction('copy_filing_guide');
    });
  }

  // -------------------------------------------------------------------------
  // Action 5: Simulated FIR (Demo Mode)
  // -------------------------------------------------------------------------
  if (btnActionFirSimulation) {
    btnActionFirSimulation.addEventListener('click', () => {
      if (modalFirSimulation) {
        // Reset sim UI state
        if (simTimelineBox) simTimelineBox.style.display = 'none';
        for (let i = 1; i <= 4; i++) {
          const stepEl = document.getElementById(`sim-step-${i}`);
          const timeEl = document.getElementById(`sim-time-${i}`);
          if (stepEl) stepEl.className = 'sim-step';
          if (timeEl) timeEl.textContent = '—';
        }
        if (btnRunFirSimulation) {
          btnRunFirSimulation.disabled = false;
          btnRunFirSimulation.textContent = '▶️ Run FIR Simulation';
        }
        modalFirSimulation.style.display = 'flex';
      }
    });
  }

  if (btnCloseSimModal && modalFirSimulation) {
    btnCloseSimModal.addEventListener('click', () => {
      modalFirSimulation.style.display = 'none';
    });
  }

  if (btnRunFirSimulation) {
    btnRunFirSimulation.addEventListener('click', async () => {
      btnRunFirSimulation.disabled = true;
      btnRunFirSimulation.textContent = 'Running Demo Simulation...';
      if (simTimelineBox) simTimelineBox.style.display = 'block';

      // Record backend demo action
      await recordComplaintAction('fir_simulation');

      const nowTime = () => new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

      // Step-by-step simulated progress animation
      const runStep = (stepNum, delayMs) => {
        return new Promise(resolve => {
          setTimeout(() => {
            const stepEl = document.getElementById(`sim-step-${stepNum}`);
            const timeEl = document.getElementById(`sim-time-${stepNum}`);
            if (stepEl) {
              stepEl.className = 'sim-step completed';
              const icon = stepEl.querySelector('.sim-step-icon');
              if (icon) icon.textContent = '✅';
            }
            if (timeEl) timeEl.textContent = `Completed at ${nowTime()}`;
            resolve();
          }, delayMs);
        });
      };

      await runStep(1, 400);
      await runStep(2, 600);
      await runStep(3, 600);
      await runStep(4, 500);

      btnRunFirSimulation.textContent = 'Simulation Completed (Demo Mode)';
      showAlert('FIR Simulation successfully completed in DEMO MODE.', 'info');
    });
  }

  // -------------------------------------------------------------------------
  // Action 6: Track Complaint Status (/helpline)
  // -------------------------------------------------------------------------
  if (btnActionTrackStatus) {
    btnActionTrackStatus.addEventListener('click', async () => {
      const ref = currentComplaint ? currentComplaint.reference_number : '';
      await recordComplaintAction('view_status');
      const targetUrl = ref ? `/helpline?ref=${encodeURIComponent(ref)}` : '/helpline';
      window.open(targetUrl, '_blank');
    });
  }

  // -------------------------------------------------------------------------
  // -------------------------------------------------------------------------
  // 9. Action: 1-Click Cybercrime Portal Auto-Filler (Option 1 Bookmarklet & Extension)
  // -------------------------------------------------------------------------
  const btnActionAutoFile = document.getElementById('btn-action-auto-file');
  const modalAutoFile = document.getElementById('modal-auto-file');
  const btnCloseAutoFileModal = document.getElementById('btn-close-autofile-modal');
  const autofillBookmarkletLink = document.getElementById('autofill-bookmarklet-link');
  const btnCopyAutofillScript = document.getElementById('btn-copy-autofill-script');
  const autofillScriptCopiedMsg = document.getElementById('autofill-script-copied-msg');
  const autofillReadyFields = document.getElementById('autofill-ready-fields');

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function getComplaintAutofillPayload() {
    if (!currentComplaint) return {};
    const f = currentComplaint.structured_fields || {};
    return {
      reference_number: currentComplaint.reference_number || 'SAI-XXXXXX',
      incident_type: f.incident_type || '',
      disputed_amount: f.financial_loss || f.disputed_amount || '',
      reported_entity: f.reported_entity || '',
      suspect_phone: f.phone_number || f.suspect_phone || '',
      suspect_account_upi: f.suspect_account_upi || '',
      suspect_channel: f.suspect_channel || '',
      incident_date: f.incident_date || '',
      victim_phone: currentComplaint.victim_phone || '',
      summary: f.summary || currentComplaint.english_summary || '',
      description: f.description || ''
    };
  }

  function setupAutofillModal() {
    const data = getComplaintAutofillPayload();
    
    // Save to localStorage so Chrome extension or tab bridge can pick it up
    try {
      localStorage.setItem('saathi_active_complaint', JSON.stringify(data));
      window.postMessage({ type: 'SAATHI_SYNC_COMPLAINT', payload: data }, '*');
    } catch(e) {}

    // 1. Generate minified bookmarklet code
    const jsonStr = JSON.stringify(data);
    const bookmarkletCode = `javascript:(function(){window.__SAATHI_COMPLAINT__=${jsonStr};var s=document.createElement('script');s.src='http://localhost:8000/portal_autofill_engine.js?t='+Date.now();s.onerror=function(){alert('Saathi AI: Could not load autofill engine. Please make sure the Saathi AI server is running on http://localhost:8000.');};document.body.appendChild(s);})();`;

    if (autofillBookmarkletLink) {
      autofillBookmarkletLink.href = bookmarkletCode;
      autofillBookmarkletLink.title = "Drag this link to your Bookmarks Bar (or click to copy code)";
    }

    // 2. Wire up script copy button
    if (btnCopyAutofillScript) {
      btnCopyAutofillScript.onclick = () => {
        navigator.clipboard.writeText(bookmarkletCode).then(() => {
          if (autofillScriptCopiedMsg) {
            autofillScriptCopiedMsg.style.display = 'block';
            setTimeout(() => { autofillScriptCopiedMsg.style.display = 'none'; }, 4000);
          }
        });
      };
    }

    // 3. Populate ready-to-paste fields drawer
    if (autofillReadyFields) {
      const items = [
        { label: 'Incident Reference', val: data.reference_number },
        { label: 'Category / Incident Type', val: data.incident_type || 'Cyber Financial Fraud' },
        { label: 'Disputed Amount', val: data.disputed_amount ? `₹${data.disputed_amount}` : '' },
        { label: 'Reported Entity / Bank', val: data.reported_entity },
        { label: 'Suspect Phone / Contact', val: data.suspect_phone },
        { label: 'Suspect Account / UPI', val: data.suspect_account_upi },
        { label: 'Incident Narrative', val: data.description || data.summary }
      ];

      autofillReadyFields.innerHTML = items.map((item, idx) => `
        <div style="display: flex; justify-content: space-between; align-items: flex-start; padding: 7px 0; border-bottom: ${idx === items.length - 1 ? 'none' : '1px solid #f1f5f9'}; gap: 8px;">
          <div style="flex: 1; word-break: break-word;">
            <strong style="color: #475569; font-size: 0.78rem;">${item.label}:</strong>
            <div style="color: #0f172a; margin-top: 2px;">${item.val ? escapeHtml(item.val) : '<em style="color:#94a3b8;">Not specified</em>'}</div>
          </div>
          ${item.val ? `
            <button type="button" class="btn-copy-field" data-val="${encodeURIComponent(item.val)}" style="background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px 8px; font-size: 0.75rem; cursor: pointer; color: #334155; white-space: nowrap; font-weight: 600;">
              📋 Copy
            </button>
          ` : ''}
        </div>
      `).join('');

      autofillReadyFields.querySelectorAll('.btn-copy-field').forEach(b => {
        b.addEventListener('click', () => {
          const textToCopy = decodeURIComponent(b.getAttribute('data-val'));
          navigator.clipboard.writeText(textToCopy).then(() => {
            const originalText = b.textContent;
            b.textContent = '✓ Copied';
            b.style.background = '#dcfce7';
            b.style.color = '#15803d';
            setTimeout(() => {
              b.textContent = originalText;
              b.style.background = '#f1f5f9';
              b.style.color = '#334155';
            }, 1800);
          });
        });
      });
    }
  }

  if (btnActionAutoFile) {
    btnActionAutoFile.addEventListener('click', () => {
      if (!modalAutoFile) return;
      modalAutoFile.style.display = 'flex';
      setupAutofillModal();
    });
  }

  if (btnCloseAutoFileModal && modalAutoFile) {
    btnCloseAutoFileModal.addEventListener('click', () => {
      modalAutoFile.style.display = 'none';
    });
  }

  // Universal top close button handler for all modals
  document.querySelectorAll('.modal-btn-close').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const parentModal = e.target.closest('.modal-backdrop');
      if (parentModal) {
        parentModal.style.display = 'none';
      }
    });
  });

  // Dismiss modal when clicking outer backdrop
  document.querySelectorAll('.modal-backdrop').forEach(backdrop => {
    backdrop.addEventListener('click', (e) => {
      if (e.target === backdrop) {
        backdrop.style.display = 'none';
      }
    });
  });

  // Close active modal on Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal-backdrop').forEach(backdrop => {
        if (backdrop.style.display !== 'none') {
          backdrop.style.display = 'none';
        }
      });
    }
  });

  // -------------------------------------------------------------------------
  // 10. Bootstrap Initialization
  // -------------------------------------------------------------------------
  startPolling();
});
