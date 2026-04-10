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
  let chatRequestInFlight = false;
  let transcribeRequestInFlight = false;
  let pendingImageBase64 = null;
  let pendingImageName = '';
  const MAX_VOICE_CAPTURE_MS = 15000;
  const recordingSession = {
    stream: null,
    audioContext: null,
    sourceNode: null,
    processorNode: null,
    chunks: [],
    sampleRate: 44100
  };
  const wsVoiceSession = {
    socket: null
  };

  function getBackendBaseUrl() {
    return (window.EPIC_CONFIG?.backendBaseUrl || '').replace(/\/+$/, '');
  }

  function getSessionId() {
    try {
      const session = typeof loadEpicSession === 'function' ? loadEpicSession() : null;
      return (
        session?.sessionId ||
        session?.session_id ||
        ''
      );
    } catch {
      return '';
    }
  }

  function getAsrLanguage() {
    return (window.EPIC_CONFIG?.asrLanguage || 'en-US').trim();
  }

  function getVoiceAsrMode() {
    return (window.EPIC_CONFIG?.voiceAsrMode || 'http').trim().toLowerCase();
  }

  function getVoiceWsBaseUrl() {
    const fromConfig = (window.EPIC_CONFIG?.voiceWsBaseUrl || '').trim();
    if (fromConfig) return fromConfig.replace(/\/+$/, '');
    const backend = getBackendBaseUrl();
    if (backend) return backend.replace(/^http/, 'ws').replace(/\/+$/, '');
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    return `${protocol}://${window.location.host}`;
  }

  function speakText(text) {
    if (activeMode !== 'voice' || !window.speechSynthesis || !text?.trim()) return;
    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = getAsrLanguage();
      window.speechSynthesis.speak(utterance);
    } catch {
      // Ignore browser TTS issues in static UI mode.
    }
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

  function downsampleTo16kHz(input, inputSampleRate) {
    if (inputSampleRate === 16000) return input;
    const ratio = inputSampleRate / 16000;
    const outLength = Math.max(1, Math.round(input.length / ratio));
    const output = new Float32Array(outLength);
    let inOffset = 0;
    for (let i = 0; i < outLength; i += 1) {
      const nextInOffset = Math.min(input.length, Math.round((i + 1) * ratio));
      let sum = 0;
      let count = 0;
      while (inOffset < nextInOffset) {
        sum += input[inOffset];
        inOffset += 1;
        count += 1;
      }
      output[i] = count ? (sum / count) : 0;
    }
    return output;
  }

  function float32ToPcm16Buffer(samples) {
    const pcm = new Int16Array(samples.length);
    for (let i = 0; i < samples.length; i += 1) {
      const clamped = Math.max(-1, Math.min(1, samples[i]));
      pcm[i] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
    }
    return pcm.buffer;
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

  function fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        if (typeof reader.result !== 'string') {
          reject(new Error('Unable to read image file.'));
          return;
        }
        const parts = reader.result.split(',', 2);
        resolve(parts.length === 2 ? parts[1] : reader.result);
      };
      reader.onerror = () => reject(new Error('Failed to read image file.'));
      reader.readAsDataURL(file);
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
    sendBtn.disabled = !hasText || chatRequestInFlight;
  }

  function setMode(mode) {
    activeMode = mode;
    document.querySelectorAll('.mode-btn[data-mode]').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.mode === mode);
    });
    input.placeholder = placeholders[mode] || placeholders.text;
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
    source.innerHTML = `<span class="msg-source-icon">*</span>${reply.source}`;

    group.appendChild(sender);
    group.appendChild(bubble);
    group.appendChild(source);
    return group;
  }

  function createStreamingAgentMessage() {
    const group = document.createElement('div');
    group.className = 'msg-group agent';

    const sender = document.createElement('div');
    sender.className = 'msg-sender';
    sender.textContent = 'Veldooc';

    const bubble = document.createElement('div');
    bubble.className = 'bubble agent';
    bubble.textContent = '';

    const source = document.createElement('div');
    source.className = 'msg-source';
    source.innerHTML = '<span class="msg-source-icon">*</span>Live response';

    group.appendChild(sender);
    group.appendChild(bubble);
    group.appendChild(source);
    return { group, bubble, source };
  }

  function createErrorReply(message, source = 'Agent error') {
    return {
      html: message || 'Agent response failed.',
      source
    };
  }

  function parseCitations(citations) {
    if (!Array.isArray(citations) || citations.length === 0) return 'No citations';
    return citations
      .map((item) => {
        const tag = item?.tag || 'CITE';
        const src = item?.resourceType || item?.sourceType || 'source';
        return `${tag}:${src}`;
      })
      .join(' | ');
  }

  function parseSseBlocks(buffer) {
    const normalized = buffer.replace(/\r\n/g, '\n');
    const blocks = normalized.split('\n\n');
    const complete = blocks.slice(0, -1);
    const rest = blocks[blocks.length - 1] || '';
    return { complete, rest };
  }

  function parseSseDataLine(block) {
    const lines = block.split('\n');
    const dataLines = lines.filter((line) => line.startsWith('data:'));
    if (!dataLines.length) return null;
    return dataLines.map((line) => line.slice(5).trim()).join('\n');
  }

  async function streamAgentReply({ sessionId, message, imageB64, modality }, streamUi) {
    const baseUrl = getBackendBaseUrl();
    if (!baseUrl) throw new Error('EPIC_CONFIG.backendBaseUrl is missing.');

    const response = await fetch(`${baseUrl}/agent/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        message,
        image_b64: imageB64 || undefined,
        modality
      })
    });

    if (!response.ok || !response.body) {
      const text = await response.text();
      throw new Error(text || `Agent request failed (${response.status}).`);
    }

    const decoder = new TextDecoder();
    const reader = response.body.getReader();
    let buffer = '';
    let finalText = '';
    let finalCitations = [];
    let sawRenderableEvent = false;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const { complete, rest } = parseSseBlocks(buffer);
      buffer = rest;

      complete.forEach((block) => {
        const payloadRaw = parseSseDataLine(block);
        if (!payloadRaw) return;
        if (payloadRaw === '[DONE]') return;

        let event;
        try {
          event = JSON.parse(payloadRaw);
        } catch {
          return;
        }

        if (event.type === 'token' && event.text) {
          sawRenderableEvent = true;
          finalText += event.text;
          streamUi.bubble.textContent = finalText;
          return;
        }

        if (event.type === 'sentence' && event.text) {
          sawRenderableEvent = true;
          if (!finalText.includes(event.text)) {
            finalText = `${finalText}${finalText ? ' ' : ''}${event.text}`.trim();
            streamUi.bubble.textContent = finalText;
          }
          return;
        }

        if (event.type === 'escalation') {
          sawRenderableEvent = true;
          finalText = event.text || 'Escalated to clinical team.';
          streamUi.bubble.textContent = finalText;
          streamUi.source.innerHTML = '<span class="msg-source-icon">*</span>Safety escalation';
          return;
        }

        if (event.type === 'error') {
          sawRenderableEvent = true;
          finalText = event.text || 'Agent failed to generate a response.';
          streamUi.bubble.textContent = finalText;
          return;
        }

        if (event.type === 'done') {
          sawRenderableEvent = true;
          finalText = (event.text || finalText || '').trim();
          finalCitations = Array.isArray(event.citations) ? event.citations : [];
          streamUi.bubble.textContent = finalText || 'No response text returned.';
          streamUi.source.innerHTML = `<span class="msg-source-icon">*</span>${parseCitations(finalCitations)}`;
        }
      });
    }

    if (buffer.trim()) {
      const { complete } = parseSseBlocks(`${buffer}\n\n`);
      complete.forEach((block) => {
        const payloadRaw = parseSseDataLine(block);
        if (!payloadRaw || payloadRaw === '[DONE]') return;
        try {
          const event = JSON.parse(payloadRaw);
          if (event.type === 'error') {
            sawRenderableEvent = true;
            finalText = event.text || 'Agent failed to generate a response.';
            streamUi.bubble.textContent = finalText;
          }
        } catch {
          // Ignore trailing fragments that are not valid JSON events.
        }
      });
    }

    if (!sawRenderableEvent) {
      streamUi.bubble.textContent = 'No response text returned.';
    }

    return { text: finalText, citations: finalCitations };
  }

  async function sendMessage(text) {
    const message = text.trim();
    if (!message || chatRequestInFlight) return;

    chatRequestInFlight = true;
    updateSendState();

    messages.appendChild(createPatientMessage(message));
    input.value = '';
    autoResize();
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
      chatRequestInFlight = false;
      updateSendState();
      return;
    }

    const sessionId = getSessionId();
    if (!sessionId) {
      messages.appendChild(
        createAgentMessage(createErrorReply('Session expired. Please connect Epic again.', 'Session error'))
      );
      scrollToBottom();
      showToast('Session expired. Please connect Epic again.');
      pendingImageBase64 = null;
      pendingImageName = '';
      chatRequestInFlight = false;
      updateSendState();
      return;
    }

    const streamUi = createStreamingAgentMessage();
    messages.appendChild(streamUi.group);
    scrollToBottom();

    try {
      const result = await streamAgentReply(
        {
          sessionId,
          message,
          imageB64: pendingImageBase64,
          modality: pendingImageBase64 ? 'image' : (activeMode === 'voice' ? 'voice' : 'text')
        },
        streamUi
      );
      speakText(result.text);
      if (pendingImageBase64) showToast(`Image "${pendingImageName || 'upload'}" sent with message.`);
    } catch (error) {
      const errorText = error?.message || 'Agent streaming failed.';
      streamUi.bubble.textContent = errorText;
      streamUi.source.innerHTML = '<span class="msg-source-icon">*</span>Agent error';
      showToast(errorText);
    } finally {
      pendingImageBase64 = null;
      pendingImageName = '';
      chatRequestInFlight = false;
      updateSendState();
      scrollToBottom();
    }
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
    if (wsVoiceSession.socket && wsVoiceSession.socket.readyState <= WebSocket.OPEN) {
      wsVoiceSession.socket.close();
    }
    wsVoiceSession.socket = null;
    releaseRecordingResources();
  }

  function bindVoiceSocketEvents(socket) {
    socket.onmessage = (event) => {
      let payload;
      try {
        payload = JSON.parse(event.data);
      } catch {
        return;
      }
      if (!payload || typeof payload.text !== 'string') return;
      if (payload.type === 'transcript_partial' || payload.type === 'transcript_final') {
        input.value = payload.text.trim();
        autoResize();
        updateSendState();
        if (payload.type === 'transcript_final') {
          showToast('Voice captured. You can edit then send.');
        }
      }
      if (payload.type === 'asr_error') {
        showToast(payload.text || 'ASR websocket returned an error.');
      }
    };
    socket.onerror = () => {
      showToast('Voice websocket connection failed.');
    };
    socket.onclose = () => {
      wsVoiceSession.socket = null;
    };
  }

  async function startRecordingViaWebsocket() {
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error('Browser microphone API is not available.');
    }
    const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextCtor) {
      throw new Error('Web Audio API is not available in this browser.');
    }
    const sessionId = getSessionId();
    if (!sessionId) {
      throw new Error('Session expired. Please connect Epic again.');
    }

    const socketUrl = `${getVoiceWsBaseUrl()}/ws/audio/${sessionId}`;
    const socket = new WebSocket(socketUrl);
    socket.binaryType = 'arraybuffer';
    bindVoiceSocketEvents(socket);
    wsVoiceSession.socket = socket;

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const audioContext = new AudioContextCtor();
    const sourceNode = audioContext.createMediaStreamSource(stream);
    const processorNode = audioContext.createScriptProcessor(4096, 1, 1);

    recordingSession.stream = stream;
    recordingSession.audioContext = audioContext;
    recordingSession.sourceNode = sourceNode;
    recordingSession.processorNode = processorNode;
    recordingSession.sampleRate = audioContext.sampleRate || 44100;

    processorNode.onaudioprocess = (event) => {
      if (!isRecording || !wsVoiceSession.socket || wsVoiceSession.socket.readyState !== WebSocket.OPEN) return;
      const floatChunk = event.inputBuffer.getChannelData(0);
      const downsampled = downsampleTo16kHz(floatChunk, recordingSession.sampleRate);
      wsVoiceSession.socket.send(float32ToPcm16Buffer(downsampled));
    };

    sourceNode.connect(processorNode);
    processorNode.connect(audioContext.destination);

    isRecording = true;
    micBtn.classList.add('recording');
    showToast('Listening (websocket)... tap mic again to stop.');

    if (recordTimer) clearTimeout(recordTimer);
    recordTimer = setTimeout(() => {
      if (!isRecording) return;
      stopRecording();
    }, MAX_VOICE_CAPTURE_MS);
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
    const voiceMode = getVoiceAsrMode();

    if (isRecording) {
      if (voiceMode === 'websocket') {
        stopRecording();
      } else {
        await stopRecordingAndTranscribe();
      }
      return;
    }

    try {
      if (voiceMode === 'websocket') {
        await startRecordingViaWebsocket();
      } else {
        await startRecording();
      }
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

  imageInput.addEventListener('change', async () => {
    const file = imageInput.files?.[0];
    if (!file) return;
    try {
      pendingImageBase64 = await fileToBase64(file);
      pendingImageName = file.name;
      input.value = `I uploaded "${file.name}". Please explain what it shows.`;
      autoResize();
      updateSendState();
      showToast(`Attached: ${file.name}`);
    } catch (error) {
      pendingImageBase64 = null;
      pendingImageName = '';
      showToast(error?.message || 'Image attachment failed.');
    } finally {
      imageInput.value = '';
    }
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
    showToast('Use this menu for export/share in the next iteration.');
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

