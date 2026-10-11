/* Runs in <head> so the right theme is set before the first paint (no flash). */
(function () {
  var t = null;
  try { t = localStorage.getItem('ctf-theme'); } catch (e) {}
  if (!t) t = window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', t);
})();
