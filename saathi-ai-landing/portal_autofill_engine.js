/**
 * Saathi AI — National Cyber Crime Portal (cybercrime.gov.in) 1-Click Auto-Filer
 * 
 * Works across both:
 * 1. https://cybercrime.gov.in/ (Angular SPA / Terms & Portal Navigation)
 * 2. https://cybervolunteer.mha.gov.in/ (Citizen Auth & CFCFRMS Reporting Forms)
 */

window.__SAATHI_AUTOFILL__ = function(complaintData) {
  // Prevent duplicate overlays
  const existingOverlay = document.getElementById('saathi-portal-overlay');
  if (existingOverlay) {
    existingOverlay.remove();
  }

  const data = complaintData || window.__SAATHI_COMPLAINT__ || {
    reference_number: 'SAI-XXXXXX',
    incident_type: 'Financial Fraud (UPI / Net Banking)',
    disputed_amount: '',
    reported_entity: '',
    suspect_phone: '',
    incident_date: new Date().toISOString().split('T')[0],
    summary: '',
    description: ''
  };

  // Helper to trigger Angular / React / DOM event updates
  function setNativeValue(element, value) {
    if (!element) return false;
    element.focus();
    element.value = value;
    element.dispatchEvent(new Event('input', { bubbles: true }));
    element.dispatchEvent(new Event('change', { bubbles: true }));
    element.dispatchEvent(new Event('blur', { bubbles: true }));
    element.style.borderColor = '#128c7e';
    element.style.backgroundColor = '#f0fdf4';
    return true;
  }

  // 1. Auto-fill logic
  let filledCount = 0;
  const filledFields = [];

  // Step A: Auto-check Terms & Conditions if on login-terms-conditions
  const acceptCheckbox = document.getElementById('accept-input') || document.querySelector('input[type="checkbox"][name*="accept"]');
  if (acceptCheckbox && !acceptCheckbox.checked) {
    acceptCheckbox.checked = true;
    acceptCheckbox.dispatchEvent(new Event('change', { bubbles: true }));
    filledCount++;
    filledFields.push('Statutory Terms Checkbox');
    const acceptBtn = document.querySelector('button.btn-success, button:has-text("I Accept")');
    if (acceptBtn) {
      acceptBtn.removeAttribute('disabled');
      acceptBtn.disabled = false;
    }
  }

  // Step B: Citizen Login inputs
  const mobileInput = document.getElementById('ContentPlaceHolder1_txt_Mobileno') || document.querySelector('input[name*="Mobileno"], input[placeholder*="Mobile"]');
  if (mobileInput && data.citizen_mobile) {
    if (setNativeValue(mobileInput, data.citizen_mobile)) {
      filledCount++;
      filledFields.push('Mobile Number');
    }
  }

  const nameInput = document.getElementById('ContentPlaceHolder1_txt_UserName') || document.querySelector('input[name*="UserName"], input[placeholder*="login id"]');
  if (nameInput && (data.citizen_name || data.reported_entity)) {
    if (setNativeValue(nameInput, data.citizen_name || 'Citizen')) {
      filledCount++;
      filledFields.push('Citizen Name');
    }
  }

  // Step C: Complaint Form - Disputed Financial Loss
  const amountInputs = document.querySelectorAll('input[id*="Amount"], input[id*="amount"], input[name*="Amount"], input[name*="amount"], input[id*="loss"], input[placeholder*="Amount"]');
  if (data.disputed_amount && amountInputs.length > 0) {
    amountInputs.forEach(inp => {
      if (setNativeValue(inp, String(data.disputed_amount))) {
        filledCount++;
        filledFields.push('Disputed Amount');
      }
    });
  }

  // Step D: Bank / Financial Intermediary
  const bankInputs = document.querySelectorAll('input[id*="Bank"], input[id*="bank"], input[name*="Bank"], input[name*="bank"], select[id*="Bank"], select[name*="bank"]');
  if (data.reported_entity && bankInputs.length > 0) {
    bankInputs.forEach(inp => {
      if (setNativeValue(inp, data.reported_entity)) {
        filledCount++;
        filledFields.push('Bank / Intermediary');
      }
    });
  }

  // Step E: Suspect Details (Phone, URL, Handle)
  const suspectInputs = document.querySelectorAll('input[id*="Suspect"], input[id*="suspect"], input[name*="Suspect"], input[name*="suspect"]');
  if (data.suspect_phone && suspectInputs.length > 0) {
    suspectInputs.forEach(inp => {
      if (setNativeValue(inp, data.suspect_phone)) {
        filledCount++;
        filledFields.push('Suspect Contact');
      }
    });
  }

  // Step F: Narrative & Incident Description
  const narrativeText = [
    `[SAATHI AI CITIZEN ASSISTED REPORT — REF: ${data.reference_number}]`,
    `Incident Type: ${data.incident_type || 'Financial Cyber Fraud'}`,
    `Reported Bank / Entity: ${data.reported_entity || 'Not Specified'}`,
    `Disputed Loss: ₹${data.disputed_amount ? Number(data.disputed_amount).toLocaleString('en-IN') : 'Unspecified'} INR`,
    `Suspect Phone / Handle: ${data.suspect_phone || 'Unknown'}`,
    `Incident Date: ${data.incident_date || 'Recent'}`,
    '',
    'FACTUAL NARRATIVE:',
    data.description || data.summary || 'Cyber fraud incident reported by victim.'
  ].join('\n');

  const textareas = document.querySelectorAll('textarea[id*="complaint"], textarea[id*="description"], textarea[id*="Description"], textarea[name*="complaint"], textarea[name*="description"], textarea');
  if (textareas.length > 0) {
    textareas.forEach(ta => {
      if (setNativeValue(ta, narrativeText)) {
        filledCount++;
        filledFields.push('Incident Narrative');
      }
    });
  }

  // 2. Inject sleek floating Saathi AI HUD
  const hud = document.createElement('div');
  hud.id = 'saathi-portal-overlay';
  hud.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    width: 360px;
    max-width: 90vw;
    background: #0f172a;
    color: #f8fafc;
    border: 2px solid #14b8a6;
    border-radius: 16px;
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    z-index: 9999999;
    padding: 16px;
    box-sizing: border-box;
    animation: saathiSlideIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  `;

  hud.innerHTML = `
    <style>
      @keyframes saathiSlideIn {
        from { transform: translateX(110%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
      }
      .saathi-hud-btn {
        background: #14b8a6;
        color: #042f2e;
        border: none;
        border-radius: 8px;
        padding: 6px 12px;
        font-weight: 700;
        font-size: 0.8rem;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        gap: 4px;
        transition: background 0.2s ease;
      }
      .saathi-hud-btn:hover { background: #2dd4bf; }
      .saathi-copy-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 6px;
        background: #1e293b;
        padding: 6px 10px;
        border-radius: 6px;
        font-size: 0.78rem;
      }
    </style>
    <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; padding-bottom: 8px; margin-bottom: 10px;">
      <div style="display: flex; align-items: center; gap: 8px;">
        <span style="font-size: 1.3rem;">🛡️</span>
        <div>
          <strong style="color: #5eead4; font-size: 0.95rem;">Saathi AI Portal Assistant</strong>
          <div style="font-size: 0.7rem; color: #94a3b8;">Case: ${data.reference_number}</div>
        </div>
      </div>
      <button id="saathi-hud-close" style="background: none; border: none; color: #94a3b8; font-size: 1.4rem; cursor: pointer; line-height: 1;">&times;</button>
    </div>

    <div style="background: ${filledCount > 0 ? '#064e3b' : '#334155'}; border-radius: 8px; padding: 8px 12px; margin-bottom: 12px; font-size: 0.82rem;">
      ${filledCount > 0 
        ? `✅ <strong>${filledCount} form elements auto-filled!</strong> (${filledFields.join(', ')})`
        : `ℹ️ Navigate to the complaint form. Click below to re-scan & fill.`
      }
    </div>

    <div style="margin-bottom: 12px;">
      <div style="font-size: 0.75rem; text-transform: uppercase; color: #94a3b8; font-weight: 700; margin-bottom: 6px;">1-Click Copy Ready Data:</div>
      
      <div class="saathi-copy-row">
        <span><strong>Amount:</strong> ₹${data.disputed_amount || '0'}</span>
        <button class="saathi-hud-btn" onclick="navigator.clipboard.writeText('${data.disputed_amount || 0}')">Copy</button>
      </div>

      <div class="saathi-copy-row">
        <span><strong>Bank/Entity:</strong> ${(data.reported_entity || 'N/A').slice(0, 16)}</span>
        <button class="saathi-hud-btn" onclick="navigator.clipboard.writeText('${(data.reported_entity || '').replace(/'/g, "\\'")}')">Copy</button>
      </div>

      <div class="saathi-copy-row">
        <span><strong>Suspect:</strong> ${data.suspect_phone || 'Unknown'}</span>
        <button class="saathi-hud-btn" onclick="navigator.clipboard.writeText('${data.suspect_phone || ''}')">Copy</button>
      </div>

      <div class="saathi-copy-row">
        <span><strong>Full Narrative</strong> (Formatted)</span>
        <button class="saathi-hud-btn" id="saathi-btn-copy-narrative">Copy</button>
      </div>
    </div>

    <div style="display: flex; gap: 8px;">
      <button class="saathi-hud-btn" style="flex: 1; justify-content: center; padding: 8px;" id="saathi-hud-refill">⚡ Re-Fill Active Page</button>
    </div>
  `;

  document.body.appendChild(hud);

  document.getElementById('saathi-hud-close').addEventListener('click', () => hud.remove());
  document.getElementById('saathi-btn-copy-narrative').addEventListener('click', () => {
    navigator.clipboard.writeText(narrativeText).then(() => {
      const b = document.getElementById('saathi-btn-copy-narrative');
      b.textContent = '✓ Copied';
      setTimeout(() => { b.textContent = 'Copy'; }, 1800);
    });
  });
  document.getElementById('saathi-hud-refill').addEventListener('click', () => {
    window.__SAATHI_AUTOFILL__(data);
  });
};

window.__SAATHI_AUTOFILL__(window.__SAATHI_COMPLAINT__);
