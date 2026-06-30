// Sybase ASE Unlock Portal — shared client-side behavior

(function initTheme() {
  const root = document.documentElement;
  const saved = window.__supTheme || null; // no localStorage use; in-memory only for this session
  const toggleBtn = document.getElementById('themeToggle');
  const icon = document.getElementById('themeIcon');

  function applyTheme(theme) {
    root.setAttribute('data-bs-theme', theme);
    window.__supTheme = theme;
    if (icon) {
      icon.className = theme === 'dark' ? 'bi bi-sun-fill' : 'bi bi-moon-stars-fill';
    }
  }

  if (saved) {
    applyTheme(saved);
  }

  if (toggleBtn) {
    toggleBtn.addEventListener('click', function () {
      const current = root.getAttribute('data-bs-theme');
      applyTheme(current === 'dark' ? 'light' : 'dark');
    });
  }
})();

/**
 * Show a Bootstrap toast notification.
 * @param {string} title
 * @param {string} message
 * @param {'success'|'danger'|'warning'|'info'} variant
 */
function showToast(title, message, variant) {
  variant = variant || 'info';
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const toastEl = document.createElement('div');
  toastEl.className = `toast align-items-center text-bg-${variant} border-0`;
  toastEl.setAttribute('role', 'alert');
  toastEl.setAttribute('aria-live', 'assertive');
  toastEl.setAttribute('aria-atomic', 'true');
  toastEl.innerHTML = `
    <div class="d-flex">
      <div class="toast-body"><strong>${title}:</strong> ${message}</div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
    </div>`;
  container.appendChild(toastEl);
  const toast = new bootstrap.Toast(toastEl, { delay: 5000 });
  toast.show();
  toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
}
