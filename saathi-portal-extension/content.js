/**
 * Saathi AI Chrome Extension — Content Script for cybercrime.gov.in
 */

console.log('[Saathi AI] Cybercrime Portal Auto-Filer active.');

// Listen for messages from popup or storage
chrome.storage.local.get(['active_complaint'], (result) => {
  if (result.active_complaint) {
    autoFillPortal(result.active_complaint);
  }
});

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'AUTO_FILL') {
    autoFillPortal(request.complaint);
    sendResponse({ status: 'done' });
  }
});

function autoFillPortal(complaint) {
  if (!complaint) return;

  function setVal(el, val) {
    if (!el || val === undefined || val === null) return false;
    el.focus();
    el.value = val;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    el.dispatchEvent(new Event('blur', { bubbles: true }));
    el.style.borderColor = '#128c7e';
    el.style.backgroundColor = '#ecfdf5';
    return true;
  }

  let count = 0;

  // 1. Check terms checkbox on cybercrime.gov.in/login-terms-conditions
  const chk = document.getElementById('accept-input') || document.querySelector('input[type="checkbox"][name*="accept"]');
  if (chk && !chk.checked) {
    chk.checked = true;
    chk.dispatchEvent(new Event('change', { bubbles: true }));
    count++;
    const btn = document.querySelector('button.btn-success, button:has-text("I Accept")');
    if (btn) {
      btn.disabled = false;
      btn.removeAttribute('disabled');
    }
  }

  // 2. Disputed Amount
  const loss = complaint.financial_loss || complaint.disputed_amount;
  if (loss) {
    const amounts = document.querySelectorAll('input[id*="Amount"], input[id*="amount"], input[name*="Amount"], input[name*="amount"], input[id*="loss"], input[placeholder*="Amount"]');
    amounts.forEach(inp => {
      if (setVal(inp, loss)) count++;
    });
  }

  // 3. Bank / Intermediary
  if (complaint.reported_entity) {
    const banks = document.querySelectorAll('input[id*="Bank"], input[id*="bank"], input[name*="Bank"], input[name*="bank"], select[id*="Bank"], select[name*="bank"]');
    banks.forEach(inp => {
      if (setVal(inp, complaint.reported_entity)) count++;
    });
  }

  // 4. Suspect Phone
  const suspect = complaint.phone_number || complaint.suspect_phone;
  if (suspect) {
    const suspects = document.querySelectorAll('input[id*="Suspect"], input[id*="suspect"], input[name*="Suspect"], input[name*="suspect"]');
    suspects.forEach(inp => {
      if (setVal(inp, suspect)) count++;
    });
  }

  // 5. Narrative Textarea
  const narrative = [
    `[SAATHI AI CITIZEN ASSISTED REPORT — REF: ${complaint.reference_number || 'N/A'}]`,
    `Incident Type: ${complaint.incident_type || 'Financial Fraud'}`,
    `Reported Entity: ${complaint.reported_entity || 'N/A'}`,
    `Disputed Loss: ₹${complaint.financial_loss || 0} INR`,
    `Suspect Phone / Contact: ${complaint.phone_number || 'Unknown'}`,
    `Incident Date: ${complaint.incident_date || 'Recent'}`,
    '',
    'FACTS & INCIDENT NARRATIVE:',
    complaint.description || complaint.summary || 'Cyber fraud reported.'
  ].join('\n');

  const textareas = document.querySelectorAll('textarea');
  textareas.forEach(ta => {
    if (setVal(ta, narrative)) count++;
  });

  // Floating notification
  showBadge(count, complaint.reference_number);
}

function showBadge(count, ref) {
  let badge = document.getElementById('saathi-ext-badge');
  if (!badge) {
    badge = document.createElement('div');
    badge.id = 'saathi-ext-badge';
    badge.style.cssText = `
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: #0f172a;
      color: #38bdf8;
      border: 2px solid #0284c7;
      padding: 12px 18px;
      border-radius: 12px;
      font-family: sans-serif;
      font-size: 13px;
      box-shadow: 0 10px 25px rgba(0,0,0,0.3);
      z-index: 99999999;
      display: flex;
      align-items: center;
      gap: 10px;
    `;
    document.body.appendChild(badge);
  }
  badge.innerHTML = `
    <span style="font-size: 1.2rem;">🛡️</span>
    <div>
      <strong style="color: #fff;">Saathi AI Auto-Filler</strong>
      <div style="color: #94a3b8; font-size: 11px;">Case ${ref}: ${count} elements auto-populated</div>
    </div>
    <button onclick="this.parentElement.remove()" style="background:none; border:none; color:#94a3b8; cursor:pointer; font-size:16px; margin-left:6px;">&times;</button>
  `;
  setTimeout(() => { if (badge) badge.remove(); }, 8000);
}
