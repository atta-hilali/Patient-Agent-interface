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

  function sendMessage(text) {
    const message = text.trim();
    if (!message) return;

    messages.appendChild(createPatientMessage(message));
    input.value = '';
    autoResize();
    updateSendState();
    scrollToBottom();

    const typing = createTypingBubble();
    messages.appendChild(typing);
    scrollToBottom();

    const reply = getStaticReply(message);
    setTimeout(() => {
      typing.remove();
      messages.appendChild(createAgentMessage(reply));
      scrollToBottom();
    }, 900);
  }

  function stopRecording() {
    isRecording = false;
    micBtn.classList.remove('recording');
    if (recordTimer) clearTimeout(recordTimer);
    recordTimer = null;
  }

  function toggleRecording() {
    setMode('voice');
    if (isRecording) {
      stopRecording();
      showToast('Voice capture stopped.');
      return;
    }

    isRecording = true;
    micBtn.classList.add('recording');
    showToast('Listening...');

    recordTimer = setTimeout(() => {
      if (!isRecording) return;
      stopRecording();
      input.value = 'What do my latest lab results mean?';
      autoResize();
      updateSendState();
      showToast('Voice captured. You can edit then send.');
    }, 1500);
  }

  sendBtn.addEventListener('click', () => {
    sendMessage(input.value);
  });

  input.addEventListener('input', () => {
    autoResize();
    updateSendState();
  });

  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      sendMessage(input.value);
    }
  });

  document.querySelectorAll('.quick-reply').forEach((btn) => {
    btn.addEventListener('click', () => sendMessage(btn.textContent || ''));
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

  micBtn.addEventListener('click', toggleRecording);

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
