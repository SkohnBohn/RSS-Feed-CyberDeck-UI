async function triggerFetch() {
  const btn = document.getElementById('fetch-btn');
  if (!btn || btn.disabled) return;
  btn.disabled = true;
  btn.textContent = 'Fetching…';

  try {
    await fetch('/fetch', { method: 'POST' });
  } catch (e) {
    btn.disabled = false;
    btn.textContent = 'Fetch Now';
    return;
  }

  const poll = setInterval(async () => {
    try {
      const res = await fetch('/fetch-status');
      const data = await res.json();
      if (!data.running) {
        clearInterval(poll);
        window.location.reload();
      }
    } catch (_) {}
  }, 2000);
}

// If the page loads while a fetch is already running, start polling immediately
document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('fetch-btn');
  if (btn && btn.textContent.trim() === 'Fetching…') {
    btn.disabled = true;
    const poll = setInterval(async () => {
      try {
        const res = await fetch('/fetch-status');
        const data = await res.json();
        if (!data.running) {
          clearInterval(poll);
          window.location.reload();
        }
      } catch (_) {}
    }, 2000);
  }
});
