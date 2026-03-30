function initChatFlow() {
  const messages = document.getElementById('messages');
  const input = document.getElementById('chat-input');
  const sendBtn = document.getElementById('chat-send-btn');
  const micBtn = document.getElementById('chat-mic-btn');
  const imageBtn = document.getElementById('chat-image-btn');
  const imageInput = document.getElementById('chat-image-input');
  const toast = document.getElementById('chat-toast');
  const privacyLink = document.getElementById('chat-privacy-link');
  const recordBtn = document.getElementById('chat-record-btn');
  const moreBtn = document.getElementById('chat-more-btn');
  const contextStrip = document.getElementById('chat-context-strip');
  if (!messages || !input || !sendBtn || !micBtn || !imageBtn || !imageInput || !toast) return;

  const placeholders = {
    text: 'Ask about your medications, appointments, labs...',
    voice: 'Tap the microphone, then send your transcribed question...',
    image: 'Upload an image and ask a question about it...'
  };

  let activeMode = 'text';
  let isRecording = false;
  let recordTimer = null;
  let toastTimer = null;
  let safetyRequestInFlight = false;
  let transcribeRequestInFlight = false;
  const MAX_VOICE_CAPTURE_MS = 15000;
  const recordingSession = {
    stream: null,
    audioContext: null,
    sourceNode: null,
    processorNode: null,
    chunks: [],
    sampleRate: 44100
  };

  function getBackendBaseUrl() {
    return (window.EPIC_CONFIG?.backendBaseUrl || '').replace(/\/+$/, '');
  }

  async function runPreflightSafetyCheck(text) {
    const baseUrl = getBackendBaseUrl();
    if (!baseUrl) return null;
    try {
      const response = await fetch(`${baseUrl}/chat/preflight`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
      });
      if (!response.ok) return null;
      return response.json();
    } catch {
      return null;
    }
  }

  function getAsrLanguage() {
    return (window.EPIC_CONFIG?.asrLanguage || 'en-US').trim();
  }

  function writeAsciiString(view, offset, value) {
    for (let i = 0; i < value.length; i += 1) {
      view.setUint8(offset + i, value.charCodeAt(i));
    }
  }

  function mergeFloatChunks(chunks) {
    const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
    const merged = new Float32Array(totalLength);
    let offset = 0;
    chunks.forEach((chunk) => {
      merged.set(chunk, offset);
      offset += chunk.length;
    });
    return merged;
  }

  function encodeMonoWav(samples, sampleRate) {
    const bytesPerSample = 2;
    const numChannels = 1;
    const blockAlign = numChannels * bytesPerSample;
    const byteRate = sampleRate * blockAlign;
    const dataSize = samples.length * bytesPerSample;
    const buffer = new ArrayBuffer(44 + dataSize);
    const view = new DataView(buffer);

    writeAsciiString(view, 0, 'RIFF');
    view.setUint32(4, 36 + dataSize, true);
    writeAsciiString(view, 8, 'WAVE');
    writeAsciiString(view, 12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, numChannels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, byteRate, true);
    view.setUint16(32, blockAlign, true);
    view.setUint16(34, 16, true);
    writeAsciiString(view, 36, 'data');
    view.setUint32(40, dataSize, true);

    let offset = 44;
    for (let i = 0; i < samples.length; i += 1) {
      const clamped = Math.max(-1, Math.min(1, samples[i]));
      const pcm = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
      view.setInt16(offset, pcm, true);
      offset += 2;
    }

    return new Blob([buffer], { type: 'audio/wav' });
  }

  function blobToBase64(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        if (typeof reader.result !== 'string') {
          reject(new Error('Unable to read audio payload.'));
          return;
        }
        const parts = reader.result.split(',', 2);
        resolve(parts.length === 2 ? parts[1] : reader.result);
      };
      reader.onerror = () => {
        reject(new Error('Failed to read recorded audio.'));
      };
      reader.readAsDataURL(blob);
    });
  }

  async function transcribeWithBackend({ audioBase64, mimeType, fileName }) {
    const baseUrl = getBackendBaseUrl();
    if (!baseUrl) {
      throw new Error('EPIC_CONFIG.backendBaseUrl is missing.');
    }

    const response = await fetch(`${baseUrl}/voice/transcribe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        audioBase64,
        mimeType,
        language: getAsrLanguage(),
        fileName
      })
    });

    const bodyText = await response.text();
    let body = {};
    if (bodyText) {
      try {
        body = JSON.parse(bodyText);
      } catch {
        body = { detail: bodyText };
      }
    }

    if (!response.ok) {
      throw new Error(body?.detail || `Voice transcription failed (${response.status}).`);
    }
    if (!body?.text) {
      throw new Error('ASR response did not include transcript text.');
    }
    return body.text;
  }

  function showToast(text) {
    toast.textContent = text;
    toast.classList.add('show');
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toast.classList.remove('show');
    }, 2200);
  }

  function scrollToBottom() {
    messages.scrollTop = messages.scrollHeight;
  }

  function autoResize() {
    input.style.height = 'auto';
    input.style.height = `${Math.min(input.scrollHeight, 100)}px`;
  }

  function updateSendState() {
    const hasText = input.value.trim().length > 0;
    sendBtn.disabled = !hasText;
  }

  function setMode(mode) {
    activeMode = mode;
    document.querySelectorAll('.mode-btn[data-mode]').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.mode === mode);
    });
    input.placeholder = placeholders[mode] || placeholders.text;
  }

  function getStaticReply(question) {
    const q = question.toLowerCase();
    if (q.includes('metformin') || q.includes('med')) {
      return {
        html: 'You currently have 6 active meds. Metformin 1000mg is typically taken with breakfast and dinner to reduce GI side effects.',
        source: 'MedicationRequest · CarePlan'
      };
    }
    if (q.includes('hba1c') || q.includes('lab')) {
      return {
        html: 'Your latest HbA1c is 7.1%. That is slightly above the common target range, so your care team may review diet, activity, and medication timing.',
        source: 'Observation · CarePlan'
      };
    }
    if (q.includes('appointment') || q.includes('bring')) {
      return {
        html: 'Your next appointment is March 22. Bring your medication list, glucose readings, and any symptom notes since your last visit.',
        source: 'Appointment · CarePlan'
      };
    }
    if (q.includes('allergy') || q.includes('penicillin')) {
      return {
        html: 'Your chart lists a penicillin allergy. I can keep warning checks active for medication questions.',
        source: 'AllergyIntolerance'
      };
    }
    return {
      html: 'I can help with medications, labs, appointments, allergies, and care plan questions from your connected record.',
      source: 'FHIR record context'
    };
  }

  function createPatientMessage(text) {
    const group = document.createElement('div');
    group.className = 'msg-group patient';
    const bubble = document.createElement('div');
    bubble.className = 'bubble patient';
    bubble.textContent = text;
    group.appendChild(bubble);
    return group;
  }

  function createAgentMessage(reply) {
    const group = document.createElement('div');
    group.className = 'msg-group agent';

    const sender = document.createElement('div');
    sender.className = 'msg-sender';
    sender.textContent = 'Veldooc';

    const bubble = document.createElement('div');
    bubble.className = 'bubble agent';
    bubble.textContent = reply.html;

    const source = document.createElement('div');
    source.className = 'msg-source';
    source.innerHTML = `<span class="msg-source-icon">⊙</span>${reply.source}`;

    group.appendChild(sender);
    group.appendChild(bubble);
    group.appendChild(source);
    return group;
  }

  function createTypingBubble() {
    const group = document.createElement('div');
    group.className = 'msg-group agent';
    group.dataset.typing = 'true';
    group.innerHTML = `
      <div class="msg-sender">Veldooc</div>
      <div class="typing-bubble">
        <div class="tdot"></div><div class="tdot"></div><div class="tdot"></div>
      </div>
    `;
    return group;
  }

  async function sendMessage(text) {
    const message = text.trim();
    if (!message || safetyRequestInFlight) return;

    safetyRequestInFlight = true;

    messages.appendChild(createPatientMessage(message));
    input.value = '';
    autoResize();
    updateSendState();
    scrollToBottom();

    const preflight = await runPreflightSafetyCheck(message);
    if (preflight?.escalate) {
      messages.appendChild(
        createAgentMessage({
          html: 'Your message may need immediate clinical review. I am escalating this to a clinician now.',
          source: 'Safety pre-flight escalation'
        })
      );
      scrollToBottom();
      showToast('Safety escalation triggered.');
      safetyRequestInFlight = false;
      return;
    }

    const typing = createTypingBubble();
    messages.appendChild(typing);
    scrollToBottom();

    const reply = getStaticReply(message);
    setTimeout(() => {
      typing.remove();
      messages.appendChild(createAgentMessage(reply));
      scrollToBottom();
      safetyRequestInFlight = false;
    }, 900);
  }

  function releaseRecordingResources() {
    if (recordingSession.processorNode) {
      recordingSession.processorNode.disconnect();
      recordingSession.processorNode.onaudioprocess = null;
    }
    if (recordingSession.sourceNode) {
      recordingSession.sourceNode.disconnect();
    }
    if (recordingSession.stream) {
      recordingSession.stream.getTracks().forEach((track) => track.stop());
    }
    if (recordingSession.audioContext) {
      void recordingSession.audioContext.close().catch(() => {});
    }

    recordingSession.stream = null;
    recordingSession.audioContext = null;
    recordingSession.sourceNode = null;
    recordingSession.processorNode = null;
  }

  function stopRecording() {
    isRecording = false;
    micBtn.classList.remove('recording');
    if (recordTimer) clearTimeout(recordTimer);
    recordTimer = null;
    recordingSession.chunks = [];
    releaseRecordingResources();
  }

  async function startRecording() {
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error('Browser microphone API is not available.');
    }

    const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextCtor) {
      throw new Error('Web Audio API is not available in this browser.');
    }

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const audioContext = new AudioContextCtor();
    const sourceNode = audioContext.createMediaStreamSource(stream);
    const processorNode = audioContext.createScriptProcessor(4096, 1, 1);

    recordingSession.stream = stream;
    recordingSession.audioContext = audioContext;
    recordingSession.sourceNode = sourceNode;
    recordingSession.processorNode = processorNode;
    recordingSession.chunks = [];
    recordingSession.sampleRate = audioContext.sampleRate || 44100;

    processorNode.onaudioprocess = (event) => {
      if (!isRecording) return;
      const channelData = event.inputBuffer.getChannelData(0);
      recordingSession.chunks.push(new Float32Array(channelData));
    };

    sourceNode.connect(processorNode);
    processorNode.connect(audioContext.destination);

    isRecording = true;
    micBtn.classList.add('recording');
    showToast('Listening... tap mic again to transcribe.');

    if (recordTimer) clearTimeout(recordTimer);
    recordTimer = setTimeout(() => {
      if (!isRecording) return;
      void stopRecordingAndTranscribe();
    }, MAX_VOICE_CAPTURE_MS);
  }

  async function stopRecordingAndTranscribe() {
    if (!isRecording || transcribeRequestInFlight) return;

    isRecording = false;
    micBtn.classList.remove('recording');
    if (recordTimer) clearTimeout(recordTimer);
    recordTimer = null;

    const chunks = recordingSession.chunks.slice();
    const sampleRate = recordingSession.sampleRate;
    recordingSession.chunks = [];
    releaseRecordingResources();

    if (!chunks.length) {
      showToast('No audio captured. Please try again.');
      return;
    }

    transcribeRequestInFlight = true;
    showToast('Transcribing voice...');

    try {
      const merged = mergeFloatChunks(chunks);
      const wavBlob = encodeMonoWav(merged, sampleRate);
      const audioBase64 = await blobToBase64(wavBlob);
      const transcript = await transcribeWithBackend({
        audioBase64,
        mimeType: 'audio/wav',
        fileName: `voice-${Date.now()}.wav`
      });
      input.value = transcript.trim();
      autoResize();
      updateSendState();
      showToast('Voice captured. You can edit then send.');
    } catch (error) {
      showToast(error?.message || 'Voice transcription failed.');
    } finally {
      transcribeRequestInFlight = false;
    }
  }

  async function toggleRecording() {
    setMode('voice');
    if (isRecording) {
      await stopRecordingAndTranscribe();
      return;
    }

    try {
      await startRecording();
    } catch (error) {
      stopRecording();
      showToast(error?.message || 'Unable to access microphone.');
    }
  }

  sendBtn.addEventListener('click', () => {
    void sendMessage(input.value);
  });

  input.addEventListener('input', () => {
    autoResize();
    updateSendState();
  });

  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void sendMessage(input.value);
    }
  });

  document.querySelectorAll('.quick-reply').forEach((btn) => {
    btn.addEventListener('click', () => {
      void sendMessage(btn.textContent || '');
    });
  });

  document.querySelectorAll('.mode-btn[data-mode]').forEach((btn) => {
    btn.addEventListener('click', () => {
      setMode(btn.dataset.mode);
      if (btn.dataset.mode === 'voice') showToast('Voice mode selected.');
      if (btn.dataset.mode === 'image') showToast('Image mode selected.');
    });
  });

  imageBtn.addEventListener('click', () => {
    setMode('image');
    imageInput.click();
  });

  imageInput.addEventListener('change', () => {
    const file = imageInput.files?.[0];
    if (!file) return;
    input.value = `I uploaded "${file.name}". Please explain what it shows.`;
    autoResize();
    updateSendState();
    showToast(`Attached: ${file.name}`);
    imageInput.value = '';
  });

  micBtn.addEventListener('click', () => {
    void toggleRecording();
  });

  recordBtn?.addEventListener('click', () => {
    const hidden = contextStrip?.classList.toggle('is-hidden');
    recordBtn.classList.toggle('active', Boolean(hidden));
    showToast(hidden ? 'Record summary hidden.' : 'Record summary shown.');
  });

  moreBtn?.addEventListener('click', () => {
    showToast('Static mode: export/share actions can be connected next.');
  });

  privacyLink?.addEventListener('click', (event) => {
    event.preventDefault();
    showToast('Privacy policy dialog is not connected yet.');
  });

  messages.addEventListener('click', (event) => {
    const cite = event.target.closest('.cite');
    if (!cite) return;
    showToast(`Source ${cite.textContent.trim()} selected.`);
  });

  document.addEventListener('screen:change', (event) => {
    if (event.detail.id !== 'screen-chat') {
      stopRecording();
      return;
    }
    setMode('text');
    autoResize();
    updateSendState();
    setTimeout(() => input.focus(), 120);
  });

  setMode('text');
  autoResize();
  updateSendState();
}
