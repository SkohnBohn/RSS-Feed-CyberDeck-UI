// ── Minimal hx-post / hx-target / hx-swap handler ───────────────────────────
// Replaces the HTMX CDN dependency so the app works fully offline.
// Handles the three attributes we use: hx-post, hx-target, hx-swap="outerHTML"

document.addEventListener('click', async (e) => {
  const btn = e.target.closest('[hx-post]');
  if (!btn) return;
  e.preventDefault();

  const url      = btn.getAttribute('hx-post');
  const targetSel = btn.getAttribute('hx-target');
  const swap     = btn.getAttribute('hx-swap') || 'outerHTML';
  const target   = targetSel ? document.querySelector(targetSel) : btn;

  if (target) target.style.transition = 'opacity 0.15s, transform 0.15s';

  const res = await fetch(url, { method: 'POST' });

  if (swap.startsWith('outerHTML') && target) {
    const html = res.status === 204 ? '' : await res.text();
    if (html) {
      target.outerHTML = html;
    } else {
      // fade out then remove
      target.style.opacity = '0';
      target.style.transform = 'translateX(6px)';
      setTimeout(() => target.remove(), 160);
    }
  }
});

// ── Fetch Now button ─────────────────────────────────────────────────────────

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
      const data = await fetch('/fetch-status').then(r => r.json());
      if (!data.running) { clearInterval(poll); window.location.reload(); }
    } catch (_) {}
  }, 2000);
}

// If the page loads mid-fetch, start polling immediately
document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('fetch-btn');
  if (btn && btn.textContent.trim() === 'Fetching…') {
    btn.disabled = true;
    const poll = setInterval(async () => {
      try {
        const data = await fetch('/fetch-status').then(r => r.json());
        if (!data.running) { clearInterval(poll); window.location.reload(); }
      } catch (_) {}
    }, 2000);
  }
});
