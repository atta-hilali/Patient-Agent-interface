function initWelcomeFlow() {
  document.getElementById('welcome-start-btn')?.addEventListener('click', () => {
    goTo('screen-ehr');
  });
  document.getElementById('welcome-existing-btn')?.addEventListener('click', () => {
    goTo('screen-ehr');
  });
}

document.addEventListener('DOMContentLoaded', () => {
  initNavigation();
  initWelcomeFlow();
  initEhrFlow();
  initLoginFlow();
  initLoadingFlow();
  initSessionTimer();
  initChatFlow();
  initEpicUi();
});
