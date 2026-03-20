function initSessionTimer() {
  let secs = 1721;
  setInterval(() => {
    secs = Math.max(0, secs - 1);
    const m = Math.floor(secs / 60);
    const s = (secs % 60).toString().padStart(2, '0');
    const el = document.getElementById('chat-timer');
    if (el) el.textContent = `${m}:${s}`;
  }, 1000);
}
