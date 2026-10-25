/**
 * Saathi AI — Voice Note Studio & Interactive Scripts
 */

document.addEventListener('DOMContentLoaded', () => {
  // -------------------------------------------------------------------------
  // 0. API Base URL Detection (Seamless support for localhost, LAN IP, tunnels)
  // -------------------------------------------------------------------------
  function getApiBaseUrl() {
    const origin = window.location.origin;
    // If running directly on backend port 8000 or served by FastAPI
    if (origin.includes(':8000') || !window.location.port) {
      return '';
    }
    // If running frontend on separate dev server (e.g. port 3000, 5500)
    const hostname = window.location.hostname || 'localhost';
    const protocol = window.location.protocol || 'http:';
    return `${protocol}//${hostname}:8000`;
  }

  const API_BASE = getApiBaseUrl();

  // -------------------------------------------------------------------------
  // 1. Mobile Menu Toggle
  // -------------------------------------------------------------------------
  const mobileToggle = document.getElementById('mobile-toggle');
  const navLinks = document.getElementById('nav-links');

  if (mobileToggle && navLinks) {
    mobileToggle.addEventListener('click', () => {
      navLinks.classList.toggle('active');
    });

    navLinks.querySelectorAll('a').forEach(link => {
      link.addEventListener('click', () => {
        navLinks.classList.remove('active');
      });
    });
  }

  // -------------------------------------------------------------------------
  // 2. FAQ Accordion Interaction
  // -------------------------------------------------------------------------
  const faqItems = document.querySelectorAll('.faq-item');
  faqItems.forEach(item => {
    const questionBtn = item.querySelector('.faq-question');
    if (questionBtn) {
      questionBtn.addEventListener('click', () => {
        const isActive = item.classList.contains('active');
        faqItems.forEach(otherItem => {
          otherItem.classList.remove('active');
          const btn = otherItem.querySelector('.faq-question');
          if (btn) btn.setAttribute('aria-expanded', 'false');
        });

        if (!isActive) {
          item.classList.add('active');
          questionBtn.setAttribute('aria-expanded', 'true');
        }
      });
    }
  });

  if (faqItems.length > 0) {
    faqItems[0].classList.add('active');
    const firstBtn = faqItems[0].querySelector('.faq-question');
    if (firstBtn) firstBtn.setAttribute('aria-expanded', 'true');
  }

  // -------------------------------------------------------------------------
  // 3. WhatsApp Chat Simulation Device
  // -------------------------------------------------------------------------
  const chatButtons = document.querySelectorAll('.chat-btn');
  const chatMessages = document.getElementById('chat-messages');

  chatButtons.forEach(btn => {
    btn.addEventListener('click', (e) => {
      const text = e.target.textContent;
      chatButtons.forEach(b => b.style.opacity = '0.5');
      e.target.style.opacity = '1';
      e.target.style.fontWeight = '800';

      const userBubble = document.createElement('div');
      userBubble.className = 'wa-bubble wa-outgoing';
      userBubble.style.marginTop = '6px';
      userBubble.innerHTML = `
        <p>${text}</p>
        <div class="wa-time">Just now <span class="blue-ticks">✓✓</span></div>
      `;
      chatMessages.appendChild(userBubble);
      chatMessages.scrollTop = chatMessages.scrollHeight;
    });
  });

  // -------------------------------------------------------------------------
  // 4. Navbar Shadow on Scroll
  // -------------------------------------------------------------------------
  const navbar = document.getElementById('navbar');
  window.addEventListener('scroll', () => {
    if (window.scrollY > 20) {
      navbar.style.boxShadow = '0 4px 20px rgba(11, 20, 26, 0.08)';
    } else {
      navbar.style.boxShadow = 'none';
    }
  });

  // =========================================================================
  // 5. VOICE NOTE STUDIO (Recording, Audio Ingestion, Upload & Status Polling)
  // =========================================================================

  // DOM Elements - Studio Tabs
  const tabRecordBtn = document.getElementById('tab-record-btn');
  const tabUploadBtn = document.getElementById('tab-upload-btn');
  const panelRecord = document.getElementById('panel-record');
  const panelUpload = document.getElementById('panel-upload');

  // DOM Elements - Live Recorder
  const btnRecord = document.getElementById('btn-record');
  const recordStatusLabel = document.getElementById('record-status-label');
  const recordHintText = document.getElementById('record-hint-text');
  const timerDisplay = document.getElementById('timer-display');
  const btnPauseRecord = document.getElementById('btn-pause-record');
  const pauseLabel = document.getElementById('pause-label');
  const btnStopRecord = document.getElementById('btn-stop-record');
  const btnDeleteRecord = document.getElementById('btn-delete-record');
  const waveformVisualizer = document.getElementById('waveform-visualizer');
  const waveformBars = document.querySelectorAll('.waveform-bar');

  // Preview elements
  const audioPreviewSection = document.getElementById('audio-preview-section');
  const previewAudioElement = document.getElementById('preview-audio-element');
  const previewDurationBadge = document.getElementById('preview-duration-badge');
  const btnReRecord = document.getElementById('btn-re-record');
  const btnSendRecorded = document.getElementById('btn-send-recorded');

  // File Upload elements
  const fileDropZone = document.getElementById('file-drop-zone');
  const audioFileInput = document.getElementById('audio-file-input');
  const fileDetailsCard = document.getElementById('file-details-card');
  const uploadFileName = document.getElementById('upload-file-name');
  const uploadFileMeta = document.getElementById('upload-file-meta');
  const uploadAudioPreview = document.getElementById('upload-audio-preview');
  const btnRemoveFile = document.getElementById('btn-remove-file');
  const btnSendFile = document.getElementById('btn-send-file');

  // Common Feedback & Progress
  const consentCheckbox = document.getElementById('consent-checkbox');
  const studioAlert = document.getElementById('studio-alert');
  const alertIcon = document.getElementById('alert-icon');
  const alertMessage = document.getElementById('alert-message');
  const studioStatusPanel = document.getElementById('studio-status-panel');
  const progressBarFill = document.getElementById('progress-bar-fill');
  const progressText = document.getElementById('progress-text');
  const pipelineStatusBadge = document.getElementById('pipeline-status-badge');
  const tokenCard = document.getElementById('token-card');
  const tokenDisplay = document.getElementById('token-display');
  const btnCopyToken = document.getElementById('btn-copy-token');
  const pipelineMessage = document.getElementById('pipeline-message');
  const btnResetStudio = document.getElementById('btn-reset-studio');

  // Stepper Elements
  const stepUploading = document.getElementById('step-uploading');
  const stepReceived = document.getElementById('step-received');
  const stepTranscribing = document.getElementById('step-transcribing');
  const stepCompleted = document.getElementById('step-completed');

  // Transcript Elements
  const transcriptCard = document.getElementById('transcript-card');
  const transcriptContent = document.getElementById('transcript-content');
  const detectedLangFlag = document.getElementById('detected-lang-flag');
  const detectedLanguageText = document.getElementById('detected-language-text');
  const btnCopyTranscript = document.getElementById('btn-copy-transcript');
  const btnRetryJob = document.getElementById('btn-retry-job');

  // Translation Elements
  const translateActionBar = document.getElementById('translate-action-bar');
  const btnTranslateEnglish = document.getElementById('btn-translate-english');
  const translateBtnIcon = document.getElementById('translate-btn-icon');
  const translateBtnText = document.getElementById('translate-btn-text');
  const alreadyEnglishNotice = document.getElementById('already-english-notice');
  const translationCard = document.getElementById('translation-card');
  const translationModelBadge = document.getElementById('translation-model-badge');
  const btnToggleTranslation = document.getElementById('btn-toggle-translation');
  const toggleTranslationIcon = document.getElementById('toggle-translation-icon');
  const toggleTranslationText = document.getElementById('toggle-translation-text');
  const translationBody = document.getElementById('translation-body');
  const translationContent = document.getElementById('translation-content');
  const btnCopyTranslation = document.getElementById('btn-copy-translation');
  const btnRetranslate = document.getElementById('btn-retranslate');
  const retranslateIcon = document.getElementById('retranslate-icon');
  const retranslateText = document.getElementById('retranslate-text');

  // Active Job State
  let currentJobToken = null;
  let currentDetectedLanguage = null;
  let currentTranscript = null;
  let currentTranslation = null;
  let isTranslationHidden = false;

  // Language flag mapping
  const LANG_FLAGS = {
    hi: '🇮🇳',
    ta: '🇮🇳',
    en: '🇬🇧',
    bn: '🇮🇳',
    te: '🇮🇳',
    mr: '🇮🇳',
    gu: '🇮🇳',
    kn: '🇮🇳',
    ml: '🇮🇳',
    pa: '🇮🇳',
    ur: '🇮🇳',
  };

  // State Variables
  const MAX_RECORDING_SECONDS = 120; // 2 minutes maximum
  const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024; // 5 MB maximum
  const ALLOWED_EXTENSIONS = ['.webm', '.ogg', '.mp3', '.wav', '.m4a'];

  let mediaRecorder = null;
  let audioStream = null;
  let audioChunks = [];
  let recordingTimer = null;
  let recordingSeconds = 0;
  let isPaused = false;
  let recordedBlob = null;
  let recordedDuration = 0;
  let selectedFile = null;
  let pollingInterval = null;
  let pollingAttempts = 0;
  const MAX_POLLING_ATTEMPTS = 60; // 60 attempts * 1.5s = 90s max wait for transcription

  // Web Audio Visualizer API
  let audioContext = null;
  let analyserNode = null;
  let visualizerAnimFrame = null;

  // -------------------------------------------------------------------------
  // Helper: Show Alert Banner
  // -------------------------------------------------------------------------
  function showAlert(message, type = 'error') {
    studioAlert.className = `studio-alert alert-${type}`;
    if (type === 'error') {
      alertIcon.textContent = '❌';
    } else if (type === 'success') {
      alertIcon.textContent = '✅';
    } else {
      alertIcon.textContent = 'ℹ️';
    }
    alertMessage.textContent = message;
    studioAlert.style.display = 'flex';
    studioAlert.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function hideAlert() {
    studioAlert.style.display = 'none';
    studioAlert.className = 'studio-alert';
  }

  // -------------------------------------------------------------------------
  // Tab Switching
  // -------------------------------------------------------------------------
  tabRecordBtn.addEventListener('click', () => {
    tabRecordBtn.classList.add('active');
    tabRecordBtn.setAttribute('aria-selected', 'true');
    tabUploadBtn.classList.remove('active');
    tabUploadBtn.setAttribute('aria-selected', 'false');
    panelRecord.classList.add('active');
    panelUpload.classList.remove('active');
    hideAlert();
  });

  tabUploadBtn.addEventListener('click', () => {
    tabUploadBtn.classList.add('active');
    tabUploadBtn.setAttribute('aria-selected', 'true');
    tabRecordBtn.classList.remove('active');
    tabRecordBtn.setAttribute('aria-selected', 'false');
    panelUpload.classList.add('active');
    panelRecord.classList.remove('active');
    hideAlert();
  });

  // -------------------------------------------------------------------------
  // Detect Supported MediaRecorder MIME Type
  // -------------------------------------------------------------------------
  function getSupportedMimeType() {
    if (!window.MediaRecorder) return null;
    const candidates = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/ogg;codecs=opus',
      'audio/mp4',
      'audio/wav',
    ];
    for (const mime of candidates) {
      if (MediaRecorder.isTypeSupported(mime)) {
        return mime;
      }
    }
    return '';
  }

  // -------------------------------------------------------------------------
  // Format Time Display Helper (mm:ss)
  // -------------------------------------------------------------------------
  function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }

  // -------------------------------------------------------------------------
  // Audio Visualizer Loop
  // -------------------------------------------------------------------------
  function startVisualizer(stream) {
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return;
      audioContext = new AudioCtx();
      analyserNode = audioContext.createAnalyser();
      analyserNode.fftSize = 64;
      const source = audioContext.createMediaStreamSource(stream);
      source.connect(analyserNode);

      const bufferLength = analyserNode.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);

      function renderFrame() {
        if (!mediaRecorder || mediaRecorder.state === 'inactive') return;
        visualizerAnimFrame = requestAnimationFrame(renderFrame);

        if (mediaRecorder.state === 'paused') {
          waveformBars.forEach(bar => (bar.style.height = '6px'));
          return;
        }

        analyserNode.getByteFrequencyData(dataArray);
        waveformBars.forEach((bar, index) => {
          const val = dataArray[index % bufferLength] || 0;
          // Scale amplitude to 6px - 44px
          const barHeight = Math.max(6, Math.min(44, (val / 255) * 44));
          bar.style.height = `${barHeight}px`;
        });
      }

      waveformVisualizer.classList.add('active');
      renderFrame();
    } catch (e) {
      console.warn('Audio visualizer fallback:', e);
    }
  }

  function stopVisualizer() {
    if (visualizerAnimFrame) {
      cancelAnimationFrame(visualizerAnimFrame);
      visualizerAnimFrame = null;
    }
    if (audioContext && audioContext.state !== 'closed') {
      audioContext.close().catch(() => {});
      audioContext = null;
    }
    waveformBars.forEach(bar => (bar.style.height = '8px'));
    waveformVisualizer.classList.remove('active');
  }

  // -------------------------------------------------------------------------
  // Recording Timer Controls
  // -------------------------------------------------------------------------
  function startTimer() {
    recordingSeconds = 0;
    timerDisplay.textContent = '00:00';
    timerDisplay.classList.remove('approaching-limit');

    recordingTimer = setInterval(() => {
      recordingSeconds += 1;
      timerDisplay.textContent = formatTime(recordingSeconds);

      // Warning when approaching 2 minutes limit
      if (recordingSeconds >= MAX_RECORDING_SECONDS - 10) {
        timerDisplay.classList.add('approaching-limit');
        recordHintText.textContent = `⚠️ Approaching 2-minute limit (${MAX_RECORDING_SECONDS - recordingSeconds}s remaining)`;
      }

      // Hard stop at 2 minutes
      if (recordingSeconds >= MAX_RECORDING_SECONDS) {
        stopRecording();
        showAlert('Maximum 2-minute recording duration reached. Audio saved for preview.', 'info');
      }
    }, 1000);
  }

  function pauseTimer() {
    clearInterval(recordingTimer);
  }

  function resumeTimer() {
    recordingTimer = setInterval(() => {
      recordingSeconds += 1;
      timerDisplay.textContent = formatTime(recordingSeconds);

      if (recordingSeconds >= MAX_RECORDING_SECONDS - 10) {
        timerDisplay.classList.add('approaching-limit');
        recordHintText.textContent = `⚠️ Approaching 2-minute limit (${MAX_RECORDING_SECONDS - recordingSeconds}s remaining)`;
      }

      if (recordingSeconds >= MAX_RECORDING_SECONDS) {
        stopRecording();
        showAlert('Maximum 2-minute recording duration reached. Audio saved for preview.', 'info');
      }
    }, 1000);
  }

  function resetTimer() {
    clearInterval(recordingTimer);
    recordingSeconds = 0;
    timerDisplay.textContent = '00:00';
    timerDisplay.classList.remove('approaching-limit');
    recordHintText.textContent = 'Tap the microphone to begin • Maximum 2 minutes (120s)';
  }

  // -------------------------------------------------------------------------
  // Start Voice Recording (Requests Microphone ONLY upon user action)
  // -------------------------------------------------------------------------
  async function startRecording() {
    hideAlert();

    // Check secure context requirement (HTTPS or localhost)
    const isLocalhost = ['localhost', '127.0.0.1'].includes(window.location.hostname);
    if (!window.isSecureContext && !isLocalhost) {
      showAlert('Microphone access requires HTTPS or localhost. Please open this site via HTTPS or localhost.', 'error');
      return;
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      showAlert('Your browser does not support audio recording. Please use the Upload Audio tab instead.', 'error');
      return;
    }

    const mimeType = getSupportedMimeType();

    try {
      // Prompt user for microphone permission
      audioStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      audioChunks = [];
      const options = mimeType ? { mimeType } : {};
      mediaRecorder = new MediaRecorder(audioStream, options);

      mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunks.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const finalMime = mimeType || mediaRecorder.mimeType || 'audio/webm';
        recordedBlob = new Blob(audioChunks, { type: finalMime });
        recordedDuration = recordingSeconds;

        // Cleanup stream tracks so browser mic indicator turns off
        if (audioStream) {
          audioStream.getTracks().forEach(track => track.stop());
          audioStream = null;
        }

        stopVisualizer();

        // Setup preview player
        const audioUrl = URL.createObjectURL(recordedBlob);
        previewAudioElement.src = audioUrl;
        previewDurationBadge.textContent = formatTime(recordedDuration);
        audioPreviewSection.style.display = 'block';

        recordStatusLabel.textContent = 'Recording complete — Transcribing audio...';
        recordHintText.textContent = 'Voice note automatically sent for speech-to-text';
        btnRecord.classList.remove('recording', 'paused');
        btnRecord.disabled = true;

        btnPauseRecord.disabled = true;
        btnStopRecord.disabled = true;
        btnDeleteRecord.disabled = false;

        // Requirement 1: Automatically send recorded note for transcription
        sendAudioData(recordedBlob, `voice_note_${Date.now()}.webm`, recordedDuration);
      };

      mediaRecorder.start(250); // Collect slices every 250ms
      isPaused = false;
      startTimer();
      startVisualizer(audioStream);

      // Update UI state
      btnRecord.classList.add('recording');
      btnRecord.classList.remove('paused');
      recordStatusLabel.textContent = 'Recording in progress...';
      recordHintText.textContent = 'Speak clearly into your microphone';

      btnPauseRecord.disabled = false;
      btnStopRecord.disabled = false;
      btnDeleteRecord.disabled = false;
      pauseLabel.textContent = 'Pause';
      audioPreviewSection.style.display = 'none';

    } catch (err) {
      console.error('Microphone error:', err);
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        showAlert('Microphone permission denied. Please allow microphone access in your browser site permissions.', 'error');
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        showAlert('No microphone was detected on your device. Please connect a microphone or use the upload tab.', 'error');
      } else {
        showAlert(`Microphone error: ${err.message || 'Unable to access microphone'}.`, 'error');
      }
      resetRecordingUI();
    }
  }

  // -------------------------------------------------------------------------
  // Pause / Resume Recording
  // -------------------------------------------------------------------------
  function togglePauseRecording() {
    if (!mediaRecorder) return;

    if (mediaRecorder.state === 'recording') {
      mediaRecorder.pause();
      isPaused = true;
      pauseTimer();
      btnRecord.classList.remove('recording');
      btnRecord.classList.add('paused');
      recordStatusLabel.textContent = 'Recording paused';
      pauseLabel.textContent = 'Resume';
    } else if (mediaRecorder.state === 'paused') {
      mediaRecorder.resume();
      isPaused = false;
      resumeTimer();
      btnRecord.classList.add('recording');
      btnRecord.classList.remove('paused');
      recordStatusLabel.textContent = 'Recording in progress...';
      pauseLabel.textContent = 'Pause';
    }
  }

  // -------------------------------------------------------------------------
  // Stop Recording
  // -------------------------------------------------------------------------
  function stopRecording() {
    if (!mediaRecorder) return;
    pauseTimer();
    if (mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
    }
  }

  // -------------------------------------------------------------------------
  // Discard / Delete Recording
  // -------------------------------------------------------------------------
  function discardRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
    }
    if (audioStream) {
      audioStream.getTracks().forEach(track => track.stop());
      audioStream = null;
    }
    stopVisualizer();
    resetRecordingUI();
    hideAlert();
  }

  function resetRecordingUI() {
    resetTimer();
    mediaRecorder = null;
    recordedBlob = null;
    audioChunks = [];
    isPaused = false;

    btnRecord.disabled = false;
    btnRecord.classList.remove('recording', 'paused');
    recordStatusLabel.textContent = 'Ready to record';
    recordHintText.textContent = 'Tap the microphone to begin • Maximum 2 minutes (120s)';

    btnPauseRecord.disabled = true;
    btnStopRecord.disabled = true;
    btnDeleteRecord.disabled = true;
    pauseLabel.textContent = 'Pause';

    audioPreviewSection.style.display = 'none';
    if (previewAudioElement.src) {
      previewAudioElement.pause();
      previewAudioElement.src = '';
    }
  }

  // Event Listeners for Recorder Buttons
  btnRecord.addEventListener('click', () => {
    if (!mediaRecorder || mediaRecorder.state === 'inactive') {
      startRecording();
    } else {
      stopRecording();
    }
  });

  btnPauseRecord.addEventListener('click', togglePauseRecording);
  btnStopRecord.addEventListener('click', stopRecording);
  btnDeleteRecord.addEventListener('click', discardRecording);
  btnReRecord.addEventListener('click', discardRecording);

  // -------------------------------------------------------------------------
  // File Upload Handling
  // -------------------------------------------------------------------------
  fileDropZone.addEventListener('click', () => {
    audioFileInput.click();
  });

  ['dragenter', 'dragover'].forEach(eventName => {
    fileDropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      fileDropZone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(eventName => {
    fileDropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      fileDropZone.classList.remove('dragover');
    });
  });

  fileDropZone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    if (dt && dt.files && dt.files.length > 0) {
      handleFileSelected(dt.files[0]);
    }
  });

  audioFileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFileSelected(e.target.files[0]);
    }
  });

  function handleFileSelected(file) {
    hideAlert();
    selectedFile = null;

    if (!file) return;

    // Validate format
    const name = file.name.toLowerCase();
    const isSupportedExt = ALLOWED_EXTENSIONS.some(ext => name.endsWith(ext));
    if (!isSupportedExt) {
      showAlert(`Unsupported file format. Please select an audio file in ${ALLOWED_EXTENSIONS.join(', ')} format.`, 'error');
      audioFileInput.value = '';
      return;
    }

    // Validate size (5 MB)
    if (file.size > MAX_FILE_SIZE_BYTES) {
      const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
      showAlert(`Selected file is too large (${sizeMB} MB). Maximum allowed size is 5 MB.`, 'error');
      audioFileInput.value = '';
      return;
    }

    if (file.size === 0) {
      showAlert('The selected audio file is empty (0 bytes). Please upload a valid recording.', 'error');
      audioFileInput.value = '';
      return;
    }

    selectedFile = file;

    // Display File Details Card
    const sizeStr = file.size > 1024 * 1024
      ? `${(file.size / (1024 * 1024)).toFixed(2)} MB`
      : `${(file.size / 1024).toFixed(1)} KB`;

    uploadFileName.textContent = file.name;
    uploadFileMeta.textContent = `${sizeStr} • ${file.type || 'audio'}`;
    uploadAudioPreview.src = URL.createObjectURL(file);
    fileDetailsCard.style.display = 'block';

    // Check duration from HTML audio metadata
    uploadAudioPreview.onloadedmetadata = () => {
      if (uploadAudioPreview.duration > MAX_RECORDING_SECONDS) {
        showAlert(`Audio duration (${Math.round(uploadAudioPreview.duration)}s) exceeds maximum limit of 2 minutes (120s).`, 'error');
        btnSendFile.disabled = true;
      } else {
        btnSendFile.disabled = false;
        uploadFileMeta.textContent = `${sizeStr} • ${formatTime(uploadAudioPreview.duration)} • ${file.type || 'audio'}`;
        // Requirement 1: Automatically send uploaded audio file for transcription
        sendAudioData(selectedFile, selectedFile.name, uploadAudioPreview.duration || 0);
      }
    };
  }

  btnRemoveFile.addEventListener('click', () => {
    selectedFile = null;
    audioFileInput.value = '';
    fileDetailsCard.style.display = 'none';
    if (uploadAudioPreview.src) {
      uploadAudioPreview.pause();
      uploadAudioPreview.src = '';
    }
    hideAlert();
  });

  // -------------------------------------------------------------------------
  // Send Audio Payload (Multipart/Form-Data with Real-time Progress)
  // -------------------------------------------------------------------------
  btnSendRecorded.addEventListener('click', () => {
    if (!recordedBlob) {
      showAlert('No recording found to send. Please record a voice note first.', 'error');
      return;
    }
    sendAudioData(recordedBlob, `voice_note_${Date.now()}.webm`, recordedDuration);
  });

  btnSendFile.addEventListener('click', () => {
    if (!selectedFile) {
      showAlert('No file selected to send. Please choose an audio file first.', 'error');
      return;
    }
    const duration = uploadAudioPreview.duration || 0;
    sendAudioData(selectedFile, selectedFile.name, duration);
  });

  function sendAudioData(blobOrFile, filename, durationSeconds) {
    hideAlert();

    // Verify Consent Checkbox
    if (consentCheckbox && !consentCheckbox.checked) {
      showAlert('Please acknowledge the privacy & zero-credential policy checkbox before submitting.', 'error');
      consentCheckbox.focus();
      return;
    }

    // Prepare FormData
    const formData = new FormData();
    formData.append('audio', blobOrFile, filename);
    if (durationSeconds && durationSeconds > 0) {
      formData.append('duration', durationSeconds.toFixed(2));
    }

    // Display Status Panel & Stepper
    studioStatusPanel.style.display = 'block';
    studioStatusPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    if (transcriptCard) transcriptCard.style.display = 'none';
    if (btnRetryJob) btnRetryJob.style.display = 'none';

    setStepperState('uploading');
    progressBarFill.style.width = '0%';
    progressText.textContent = 'Uploading audio payload... 0%';
    pipelineStatusBadge.textContent = 'Uploading';
    tokenCard.style.display = 'none';
    btnResetStudio.style.display = 'none';
    pipelineMessage.textContent = 'Transmitting audio securely to temporary intake spool...';

    // Use XMLHttpRequest for actual client-side progress events
    const xhr = new XMLHttpRequest();
    const endpoint = `${API_BASE}/api/voice`;

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        const percent = Math.round((e.loaded / e.total) * 100);
        progressBarFill.style.width = `${percent}%`;
        progressText.textContent = `Uploading audio payload... ${percent}%`;
      }
    };

    xhr.onload = () => {
      if (xhr.status === 201 || xhr.status === 200) {
        try {
          const resp = JSON.parse(xhr.responseText);
          const token = resp.token;

          // Store token in localStorage
          try {
            localStorage.setItem('saathi_last_voice_token', token);
          } catch (e) {}

          // Update Stepper to Received
          progressBarFill.style.width = '100%';
          progressText.textContent = 'Upload complete (100%)';
          setStepperState('received');
          pipelineStatusBadge.textContent = 'Received';

          tokenDisplay.textContent = token;
          tokenCard.style.display = 'flex';
          pipelineMessage.innerHTML = `<strong>Audio Received:</strong> Format: <code>${resp.format || 'valid'}</code> • Size: <code>${(resp.size_bytes / 1024).toFixed(1)} KB</code>. Spooled for local transcription.`;

          // Begin Polling Status Endpoint
          startPollingStatus(token);

        } catch (parseErr) {
          showUploadFailure('Invalid response received from server.');
        }
      } else {
        let errorDetail = `Upload rejected (HTTP ${xhr.status})`;
        try {
          const errObj = JSON.parse(xhr.responseText);
          if (errObj.detail) {
            errorDetail = errObj.detail;
          }
        } catch (e) {}
        showUploadFailure(errorDetail);
      }
    };

    xhr.onerror = () => {
      showUploadFailure('Network connection error while uploading audio. Please verify backend is running.');
    };

    xhr.open('POST', endpoint, true);
    xhr.send(formData);
  }

  function showUploadFailure(message) {
    setStepperState('failed');
    progressBarFill.style.width = '100%';
    progressBarFill.style.background = '#ef4444';
    progressText.textContent = 'Upload Failed';
    pipelineStatusBadge.textContent = 'Failed';
    pipelineMessage.textContent = message;
    showAlert(message, 'error');
    btnResetStudio.style.display = 'inline-flex';
    if (btnRetryJob) btnRetryJob.style.display = 'inline-flex';
  }

  // -------------------------------------------------------------------------
  // Stepper State Controller
  // -------------------------------------------------------------------------
  function setStepperState(state) {
    const steps = [stepUploading, stepReceived, stepTranscribing, stepCompleted];
    steps.forEach(s => {
      if (s) s.classList.remove('active', 'completed', 'failed');
    });

    if (state === 'uploading') {
      if (stepUploading) stepUploading.classList.add('active');
    } else if (state === 'received') {
      if (stepUploading) stepUploading.classList.add('completed');
      if (stepReceived) stepReceived.classList.add('active');
    } else if (state === 'transcribing') {
      if (stepUploading) stepUploading.classList.add('completed');
      if (stepReceived) stepReceived.classList.add('completed');
      if (stepTranscribing) stepTranscribing.classList.add('active');
    } else if (state === 'completed') {
      if (stepUploading) stepUploading.classList.add('completed');
      if (stepReceived) stepReceived.classList.add('completed');
      if (stepTranscribing) stepTranscribing.classList.add('completed');
      if (stepCompleted) stepCompleted.classList.add('completed');
    } else if (state === 'failed') {
      if (stepUploading) stepUploading.classList.add('failed');
      if (stepReceived) stepReceived.classList.add('failed');
      if (stepTranscribing) stepTranscribing.classList.add('failed');
    }
  }

  // -------------------------------------------------------------------------
  // Status Endpoint Polling (GET /api/voice/status/{token})
  // -------------------------------------------------------------------------
  function startPollingStatus(token) {
    if (pollingInterval) clearInterval(pollingInterval);
    pollingAttempts = 0;

    const statusEndpoint = `${API_BASE}/api/voice/status/${token}`;

    pollingInterval = setInterval(async () => {
      pollingAttempts += 1;

      try {
        const res = await fetch(statusEndpoint);
        if (res.ok) {
          const data = await res.json();
          const currentStatus = data.status;

          if (currentStatus === 'received') {
            setStepperState('received');
            pipelineStatusBadge.textContent = 'Received';
            pipelineMessage.textContent = 'Audio queued in temporary buffer. Initializing local Whisper engine...';
          } else if (currentStatus === 'transcribing') {
            setStepperState('transcribing');
            pipelineStatusBadge.textContent = 'Transcribing';
            pipelineMessage.innerHTML = '⚡ <strong>Transcribing audio locally...</strong> Faster-Whisper running on backend. Preserving original spoken dialect.';
          } else if (currentStatus === 'completed') {
            clearInterval(pollingInterval);
            pollingInterval = null;
            setStepperState('completed');
            pipelineStatusBadge.textContent = 'Completed';
            pipelineMessage.innerHTML = `✅ <strong>Transcription Completed!</strong> Spoken language detected and preserved. Temporary audio file purged.`;

            currentJobToken = token;
            currentTranscript = data.transcript;
            currentDetectedLanguage = data.language;
            currentTranslation = data.english_translation || null;

            // Display Transcript Card
            if (transcriptCard && data.transcript) {
              transcriptContent.textContent = data.transcript;
              const flag = LANG_FLAGS[data.language] || '🌐';
              const langName = data.language_name || (data.language ? data.language.toUpperCase() : 'Detected');
              const conf = data.language_probability ? ` (${Math.round(data.language_probability * 100)}% conf)` : '';
              if (detectedLangFlag) detectedLangFlag.textContent = flag;
              if (detectedLanguageText) detectedLanguageText.textContent = `${langName}${conf}`;
              transcriptCard.style.display = 'block';
              transcriptCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

              // Handle English detection: if speech is already English, notify user
              const isEnglish = (data.language === 'en');
              if (alreadyEnglishNotice) {
                alreadyEnglishNotice.style.display = isEnglish ? 'inline-flex' : 'none';
              }
              if (btnTranslateEnglish) {
                btnTranslateEnglish.disabled = false;
                translateBtnIcon.textContent = '🌐';
                translateBtnText.textContent = isEnglish ? 'Translate to English (Optional)' : 'Translate to English';
              }

              // If translation was already generated/cached, render it directly
              if (data.english_translation) {
                renderTranslation(data.english_translation, isEnglish);
              } else if (translationCard) {
                translationCard.style.display = 'none';
              }
            }

            showAlert('Audio transcribed locally in original language without external leaks!', 'success');
            btnResetStudio.style.display = 'inline-flex';
            if (btnRetryJob) btnRetryJob.style.display = 'none';
            return;
          } else if (currentStatus === 'failed') {
            clearInterval(pollingInterval);
            pollingInterval = null;
            showUploadFailure(data.error_message || 'Transcription processing failed.');
            if (btnRetryJob) btnRetryJob.style.display = 'inline-flex';
            return;
          }
        }
      } catch (err) {
        console.warn('Polling error:', err);
      }

      if (pollingAttempts >= MAX_POLLING_ATTEMPTS) {
        clearInterval(pollingInterval);
        pollingInterval = null;
        setStepperState('failed');
        pipelineStatusBadge.textContent = 'Timeout';
        pipelineMessage.innerHTML = `⚠️ Transcription timed out after 90 seconds. Please retry with a shorter audio note.`;
        btnResetStudio.style.display = 'inline-flex';
        if (btnRetryJob) btnRetryJob.style.display = 'inline-flex';
      }
    }, 1500); // Poll every 1.5s
  }

  // -------------------------------------------------------------------------
  // Copy Token to Clipboard
  // -------------------------------------------------------------------------
  btnCopyToken.addEventListener('click', () => {
    const token = tokenDisplay.textContent;
    if (token) {
      navigator.clipboard.writeText(token).then(() => {
        btnCopyToken.textContent = '✓ Copied!';
        setTimeout(() => {
          btnCopyToken.innerHTML = '<span>📋 Copy Token</span>';
        }, 2000);
      }).catch(() => {
        const textarea = document.createElement('textarea');
        textarea.value = token;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        btnCopyToken.textContent = '✓ Copied!';
        setTimeout(() => {
          btnCopyToken.innerHTML = '<span>📋 Copy Token</span>';
        }, 2000);
      });
    }
  });

  // -------------------------------------------------------------------------
  // Copy Transcript to Clipboard
  // -------------------------------------------------------------------------
  if (btnCopyTranscript) {
    btnCopyTranscript.addEventListener('click', () => {
      const text = transcriptContent ? transcriptContent.textContent : '';
      if (text) {
        navigator.clipboard.writeText(text).then(() => {
          btnCopyTranscript.textContent = '✓ Copied!';
          setTimeout(() => {
            btnCopyTranscript.innerHTML = '<span>📋 Copy Transcript</span>';
          }, 2000);
        }).catch(() => {
          const textarea = document.createElement('textarea');
          textarea.value = text;
          document.body.appendChild(textarea);
          textarea.select();
          document.execCommand('copy');
          document.body.removeChild(textarea);
          btnCopyTranscript.textContent = '✓ Copied!';
          setTimeout(() => {
            btnCopyTranscript.innerHTML = '<span>📋 Copy Transcript</span>';
          }, 2000);
        });
      }
    });
  }

  // -------------------------------------------------------------------------
  // Translation Methods (POST /api/voice/translate)
  // -------------------------------------------------------------------------
  async function requestTranslation(forceRefresh = false) {
    if (!currentJobToken) {
      showAlert('No active voice note token found to translate. Please record or upload an audio file first.', 'error');
      return;
    }

    // Do not translate again if already available, unless user explicitly requests it
    if (currentTranslation && !forceRefresh) {
      renderTranslation(currentTranslation, currentDetectedLanguage === 'en');
      return;
    }

    hideAlert();
    btnTranslateEnglish.disabled = true;
    translateBtnIcon.innerHTML = '<span class="spinner"></span>';
    translateBtnText.textContent = 'Translating transcript locally...';

    try {
      const res = await fetch(`${API_BASE}/api/voice/translate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: currentJobToken, force_refresh: forceRefresh }),
      });

      const data = await res.json();
      if (res.ok) {
        currentTranslation = data.english_translation;
        renderTranslation(data.english_translation, data.is_already_english, data.engine_used);
        showAlert('English translation generated locally without external API leaks!', 'success');
        btnTranslateEnglish.disabled = false;
        translateBtnIcon.textContent = '✓';
        translateBtnText.textContent = 'Translated to English';
      } else {
        const errorDetail = data.detail || 'Translation failed on local engine.';
        showAlert(`Translation failed: ${errorDetail}`, 'error');
        btnTranslateEnglish.disabled = false;
        translateBtnIcon.textContent = '🔄';
        translateBtnText.textContent = 'Retry Translation';
      }
    } catch (err) {
      showAlert(`Network error while requesting translation: ${err.message || 'Server unreachable'}`, 'error');
      btnTranslateEnglish.disabled = false;
      translateBtnIcon.textContent = '🔄';
      translateBtnText.textContent = 'Retry Translation';
    }
  }

  function renderTranslation(translationText, isAlreadyEnglish = false, engine = '') {
    if (!translationText) return;
    translationContent.textContent = translationText;
    translationCard.style.display = 'block';
    if (translationBody) translationBody.classList.remove('collapsed');
    const footer = document.querySelector('.translation-footer');
    if (footer) footer.classList.remove('collapsed');
    isTranslationHidden = false;
    if (toggleTranslationText) toggleTranslationText.textContent = 'Hide Translation';
    if (toggleTranslationIcon) toggleTranslationIcon.textContent = '👁️';

    if (translationModelBadge) {
      if (isAlreadyEnglish) {
        translationModelBadge.textContent = 'English Original';
      } else if (engine) {
        translationModelBadge.textContent = `Local: ${engine}`;
      } else {
        translationModelBadge.textContent = 'Local Translation';
      }
    }

    translationCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  if (btnTranslateEnglish) {
    btnTranslateEnglish.addEventListener('click', () => {
      const isAlreadyVisible = (translationCard && translationCard.style.display !== 'none');
      requestTranslation(isAlreadyVisible);
    });
  }

  if (btnRetranslate) {
    btnRetranslate.addEventListener('click', () => {
      requestTranslation(true);
    });
  }

  // Hide / Show Translation Toggle
  if (btnToggleTranslation) {
    btnToggleTranslation.addEventListener('click', () => {
      isTranslationHidden = !isTranslationHidden;
      const footer = document.querySelector('.translation-footer');
      if (isTranslationHidden) {
        if (translationBody) translationBody.classList.add('collapsed');
        if (footer) footer.classList.add('collapsed');
        if (toggleTranslationText) toggleTranslationText.textContent = 'Show Translation';
        if (toggleTranslationIcon) toggleTranslationIcon.textContent = '👁️‍🗨️';
      } else {
        if (translationBody) translationBody.classList.remove('collapsed');
        if (footer) footer.classList.remove('collapsed');
        if (toggleTranslationText) toggleTranslationText.textContent = 'Hide Translation';
        if (toggleTranslationIcon) toggleTranslationIcon.textContent = '👁️';
      }
    });
  }

  // Copy Translation to Clipboard
  if (btnCopyTranslation) {
    btnCopyTranslation.addEventListener('click', () => {
      const text = translationContent ? translationContent.textContent : '';
      if (text) {
        navigator.clipboard.writeText(text).then(() => {
          btnCopyTranslation.textContent = '✓ Copied!';
          setTimeout(() => {
            btnCopyTranslation.innerHTML = '<span>📋 Copy Translation</span>';
          }, 2000);
        }).catch(() => {
          const textarea = document.createElement('textarea');
          textarea.value = text;
          document.body.appendChild(textarea);
          textarea.select();
          document.execCommand('copy');
          document.body.removeChild(textarea);
          btnCopyTranslation.textContent = '✓ Copied!';
          setTimeout(() => {
            btnCopyTranslation.innerHTML = '<span>📋 Copy Translation</span>';
          }, 2000);
        });
      }
    });
  }

  // -------------------------------------------------------------------------
  // Retry Job Button
  // -------------------------------------------------------------------------
  if (btnRetryJob) {
    btnRetryJob.addEventListener('click', () => {
      hideAlert();
      btnRetryJob.style.display = 'none';
      if (recordedBlob) {
        sendAudioData(recordedBlob, `voice_note_${Date.now()}.webm`, recordedDuration);
      } else if (selectedFile) {
        const duration = uploadAudioPreview.duration || 0;
        sendAudioData(selectedFile, selectedFile.name, duration);
      } else {
        btnResetStudio.click();
      }
    });
  }

  // -------------------------------------------------------------------------
  // Reset Studio Button
  // -------------------------------------------------------------------------
  btnResetStudio.addEventListener('click', () => {
    if (pollingInterval) clearInterval(pollingInterval);
    pollingInterval = null;

    discardRecording();
    if (selectedFile) {
      btnRemoveFile.click();
    }

    currentJobToken = null;
    currentTranscript = null;
    currentDetectedLanguage = null;
    currentTranslation = null;

    studioStatusPanel.style.display = 'none';
    progressBarFill.style.width = '0%';
    progressBarFill.style.background = 'linear-gradient(90deg, var(--wa-primary) 0%, var(--wa-accent) 100%)';
    tokenCard.style.display = 'none';
    if (transcriptCard) transcriptCard.style.display = 'none';
    if (translationCard) translationCard.style.display = 'none';
    if (alreadyEnglishNotice) alreadyEnglishNotice.style.display = 'none';
    if (btnTranslateEnglish) {
      btnTranslateEnglish.disabled = false;
      translateBtnIcon.textContent = '🌐';
      translateBtnText.textContent = 'Translate to English';
    }
    if (btnRetryJob) btnRetryJob.style.display = 'none';
    btnResetStudio.style.display = 'none';
    hideAlert();

    // Scroll back to studio top
    document.getElementById('voice-studio').scrollIntoView({ behavior: 'smooth' });
  });

});
