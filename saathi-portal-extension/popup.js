document.addEventListener('DOMContentLoaded', () => {
  const activeRef = document.getElementById('active-ref');
  const detailAmount = document.getElementById('detail-amount');
  const detailBank = document.getElementById('detail-bank');
  const detailSuspect = document.getElementById('detail-suspect');
  const btnAutofillNow = document.getElementById('btn-autofill-now');

  let currentComplaint = null;

  // Retrieve complaint stored from Saathi AI review page
  chrome.storage.local.get(['active_complaint'], (res) => {
    if (res.active_complaint) {
      currentComplaint = res.active_complaint;
      activeRef.textContent = `Case: ${currentComplaint.reference_number || 'Loaded'}`;
      detailAmount.textContent = `Amount: ₹${currentComplaint.financial_loss || currentComplaint.disputed_amount || 0}`;
      detailBank.textContent = `Entity: ${currentComplaint.reported_entity || 'N/A'}`;
      detailSuspect.textContent = `Suspect: ${currentComplaint.phone_number || currentComplaint.suspect_phone || 'N/A'}`;
    }
  });

  btnAutofillNow.addEventListener('click', async () => {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab) {
      chrome.tabs.sendMessage(tab.id, {
        action: 'AUTO_FILL',
        complaint: currentComplaint
      }, (response) => {
        btnAutofillNow.textContent = '✓ Fields Auto-Filled!';
        setTimeout(() => { btnAutofillNow.textContent = '⚡ Auto-Fill Active Portal Tab'; }, 2000);
      });
    }
  });
});
