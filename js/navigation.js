const screenIds = new Set([
  'screen-welcome',
  'screen-ehr',
  'screen-login',
  'screen-loading',
  'screen-chat'
]);

let currentScreenId = null;

function getScreenFromHash() {
  const route = window.location.hash.replace('#', '').trim();
  const candidate = route ? `screen-${route}` : 'screen-welcome';
  return screenIds.has(candidate) ? candidate : 'screen-welcome';
}

function emitScreenChange(id) {
  document.dispatchEvent(new CustomEvent('screen:change', { detail: { id } }));
}

function goTo(id, syncHash = true) {
  if (!screenIds.has(id)) return;
  const target = document.getElementById(id);
  if (!target) return;

  if (currentScreenId === id) {
    if (syncHash) {
      const route = `#${id.replace('screen-', '')}`;
      if (window.location.hash !== route) window.location.hash = route;
    }
    return;
  }

  document.querySelectorAll('.screen').forEach((screen) => {
    screen.classList.remove('active');
  });
  target.classList.add('active');
  currentScreenId = id;

  if (syncHash) {
    const route = `#${id.replace('screen-', '')}`;
    if (window.location.hash !== route) window.location.hash = route;
  }

  emitScreenChange(id);
}

function initNavigation() {
  goTo(getScreenFromHash(), false);
  window.addEventListener('hashchange', () => {
    goTo(getScreenFromHash(), false);
  });
}
