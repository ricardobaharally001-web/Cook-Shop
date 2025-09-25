// Minimal enhancements for the restaurant menu site
// - Auto-dismiss Bootstrap alerts after 4 seconds
// - No other behavior is required; feel free to extend

(function () {
  const AUTO_DISMISS_MS = 4000;
  window.addEventListener('load', () => {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach((el) => {
      setTimeout(() => {
        // Use Bootstrap's JS API if available, else fall back to removing
        try {
          const alert = bootstrap?.Alert?.getOrCreateInstance(el);
          alert?.close();
        } catch (e) {
          el.remove();
        }
      }, AUTO_DISMISS_MS);
    });
  });
})();
