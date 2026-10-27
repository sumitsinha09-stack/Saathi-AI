/**
 * Saathi AI — Complaint Status Tracker & Helpline Client
 * Phase 6 Implementation
 */

document.addEventListener('DOMContentLoaded', () => {
  const lookupForm = document.getElementById('lookup-form');
  const refInput = document.getElementById('ref-input');
  const btnTrack = document.getElementById('btn-track');
  const statusAlert = document.getElementById('status-alert');
  const alertIcon = document.getElementById('alert-icon');
  const alertMessage = document.getElementById('alert-message');
  const lookupLoading = document.getElementById('lookup-loading');
  const resultsCard = document.getElementById('results-card');

  const resultRef = document.getElementById('result-ref');
  const resultStatusPill = document.getElementById('result-status-pill');
  const resultCreated = document.getElementById('result-created');
  const resultConfirmed = document.getElementById('result-confirmed');
  const timelineList = document.getElementById('timeline-list');

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

  function showAlert(message, type = 'error') {
    if (!statusAlert) return;
    statusAlert.className = `status-alert ${type}`;
    alertIcon.textContent = (type === 'info') ? 'ℹ️' : '⚠️';
    alertMessage.textContent = message;
    statusAlert.style.display = 'flex';
  }

  function hideAlert() {
    if (statusAlert) statusAlert.style.display = 'none';
  }

  function formatDateTime(isoString) {
    if (!isoString) return 'Not recorded';
    try {
      const dt = new Date(isoString);
      return dt.toLocaleDateString('en-IN', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return String(isoString);
    }
  }

  async function performLookup(refNumber) {
    hideAlert();
    resultsCard.style.display = 'none';

    const cleanRef = (refNumber || '').trim().toUpperCase();
    if (!cleanRef) {
      showAlert('Please enter a Saathi AI reference number.');
      return;
    }

    // Format check: SAI-XXXXXX (6 alphanumeric characters)
    const refRegex = /^SAI-[A-Z0-9]{6}$/;
    if (!refRegex.test(cleanRef)) {
      showAlert('Invalid format. Reference number must be in the format SAI-XXXXXX (e.g. SAI-AB1234).');
      return;
    }

    lookupLoading.style.display = 'block';
    btnTrack.disabled = true;

    try {
      const url = `${API_BASE}/api/complaints/public-lookup/${encodeURIComponent(cleanRef)}`;
      const resp = await fetch(url);

      if (resp.status === 404) {
        throw new Error('Complaint not found or invalid reference number.');
      } else if (resp.status === 429) {
        throw new Error('Too many requests. Please wait a minute before querying again.');
      } else if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to query complaint status.');
      }

      const data = await resp.json();
      renderLookupResult(data);
    } catch (err) {
      showAlert(err.message, 'error');
    } finally {
      lookupLoading.style.display = 'none';
      btnTrack.disabled = false;
    }
  }

  function renderLookupResult(data) {
    if (!data) return;

    // Header info
    resultRef.textContent = data.reference_number || 'UNKNOWN';

    const st = (data.status || 'awaiting_review').toLowerCase();
    resultStatusPill.textContent = st.replace('_', ' ').toUpperCase();
    if (st === 'confirmed') {
      resultStatusPill.className = 'status-pill status-confirmed';
    } else if (st === 'cancelled') {
      resultStatusPill.className = 'status-pill status-cancelled';
    } else {
      resultStatusPill.className = 'status-pill status-awaiting';
    }

    resultCreated.textContent = formatDateTime(data.created_at);
    resultConfirmed.textContent = data.confirmed_at ? formatDateTime(data.confirmed_at) : 'Pending Confirmation';

    // Timeline entries
    timelineList.innerHTML = '';
    const events = data.timeline || [];

    if (events.length === 0) {
      const emptyItem = document.createElement('div');
      emptyItem.className = 'timeline-entry';
      emptyItem.innerHTML = '<p class="timeline-note">No timeline events recorded yet.</p>';
      timelineList.appendChild(emptyItem);
    } else {
      events.forEach(ev => {
        const item = document.createElement('div');
        const isDemo = Boolean(ev.is_demo);
        item.className = `timeline-entry ${isDemo ? 'demo-event' : ''}`;

        const statusLabel = (ev.status || 'STATUS').toUpperCase();
        const timeLabel = formatDateTime(ev.created_at);
        const demoBadge = isDemo ? '<span class="demo-pill">DEMO SIMULATION</span>' : '';

        item.innerHTML = `
          <div class="timeline-head">
            <span class="timeline-status">${escapeHtml(statusLabel)}</span>
            ${demoBadge}
            <span class="timeline-time">${escapeHtml(timeLabel)}</span>
          </div>
          <p class="timeline-note">${escapeHtml(ev.note || 'Status updated.')}</p>
        `;
        timelineList.appendChild(item);
      });
    }

    resultsCard.style.display = 'block';
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  // Handle form submission
  if (lookupForm) {
    lookupForm.addEventListener('submit', (e) => {
      e.preventDefault();
      performLookup(refInput.value);
    });
  }

  // Auto-uppercase input and auto-insert "SAI-" prefix if user types suffix
  if (refInput) {
    refInput.addEventListener('input', () => {
      let val = refInput.value.toUpperCase();
      if (val && !val.startsWith('SAI-') && !'SAI-'.startsWith(val)) {
        val = 'SAI-' + val.replace(/^SAI-?/i, '');
      }
      refInput.value = val;
    });
  }

  // Check URL query param e.g. /helpline?ref=SAI-XXXXXX
  const urlParams = new URLSearchParams(window.location.search);
  const initialRef = urlParams.get('ref') || urlParams.get('reference');
  if (initialRef) {
    refInput.value = initialRef.toUpperCase();
    performLookup(initialRef);
  }
});
