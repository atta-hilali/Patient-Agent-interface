function showMfa() {
  document.getElementById('login-step-credentials').style.display = 'none';
  document.getElementById('login-step-mfa').style.display = 'block';
}

function showConsent() {
  document.getElementById('login-step-mfa').style.display = 'none';
  document.getElementById('login-step-consent').style.display = 'block';
}

function resetLoginFlow() {
  document.getElementById('login-step-credentials').style.display = 'block';
  document.getElementById('login-step-mfa').style.display = 'none';
  document.getElementById('login-step-consent').style.display = 'none';
}

function initLoginFlow() {
  document.getElementById('login-signin-btn')?.addEventListener('click', showMfa);
  document.getElementById('login-verify-btn')?.addEventListener('click', showConsent);
  document.getElementById('login-allow-btn')?.addEventListener('click', () => goTo('screen-loading'));
  document.getElementById('login-deny-btn')?.addEventListener('click', () => goTo('screen-ehr'));

  document.addEventListener('screen:change', (event) => {
    if (event.detail.id === 'screen-login') resetLoginFlow();
  });
}
