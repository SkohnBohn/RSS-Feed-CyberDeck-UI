// ── Minimal hx-post / hx-target / hx-swap handler ───────────────────────────
document.addEventListener('click', async (e) => {
  const btn = e.target.closest('[hx-post]');
  if (!btn) return;
  e.preventDefault();

  const url       = btn.getAttribute('hx-post');
  const targetSel = btn.getAttribute('hx-target');
  const swap      = btn.getAttribute('hx-swap') || 'outerHTML';
  const target    = targetSel ? document.querySelector(targetSel) : btn;

  if (target) target.style.transition = 'opacity 0.15s, transform 0.15s';

  const res = await fetch(url, { method: 'POST' });

  if (swap.startsWith('outerHTML') && target) {
    const html = res.status === 204 ? '' : await res.text();
    if (html) {
      target.outerHTML = html;
    } else {
      target.style.opacity   = '0';
      target.style.transform = 'translateX(6px)';
      setTimeout(() => target.remove(), 160);
    }
  }
});

// ── Fetch Now button ─────────────────────────────────────────────────────────
async function triggerFetch() {
  const btn = document.getElementById('fetch-btn');
  if (!btn || btn.disabled) return;
  btn.disabled    = true;
  btn.textContent = 'Fetching…';
  try {
    await fetch('/fetch', { method: 'POST' });
  } catch {
    btn.disabled    = false;
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

  // Touch session — record that the river was opened, so next visit shows a marker
  if (document.getElementById('article-list') && window.location.pathname === '/river') {
    setTimeout(() => fetch('/touch-session', { method: 'POST' }).catch(() => {}), 500);
  }

  applyKeywordFilters();
  setupKeyboardTriage();
});

// ── Keyword filters ──────────────────────────────────────────────────────────
function applyKeywordFilters() {
  const list = document.getElementById('article-list');
  if (!list) return;

  const emphasize = (list.dataset.emphasize || '').split(',').filter(Boolean);
  const suppress  = (list.dataset.suppress  || '').split(',').filter(Boolean);

  if (!emphasize.length && !suppress.length) return;

  const cards = list.querySelectorAll('.card');
  let suppressedCount = 0;

  cards.forEach(card => {
    const titleEl    = card.querySelector('.card-title');
    const abstractEl = card.querySelector('.card-abstract');
    const text       = ((titleEl?.textContent || '') + ' ' + (abstractEl?.textContent || '')).toLowerCase();

    // Suppression check — hide the card if any suppress keyword matches
    if (suppress.some(kw => text.includes(kw.toLowerCase()))) {
      card.classList.add('card--suppressed');
      suppressedCount++;
      return;
    }

    // Emphasis — highlight in title and abstract
    if (emphasize.length) {
      [titleEl, abstractEl].forEach(el => {
        if (!el) return;
        let html = el.innerHTML;
        emphasize.forEach(kw => {
          if (!kw) return;
          const re = new RegExp(`(${kw.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
          html = html.replace(re, '<mark class="kw-emphasis">$1</mark>');
        });
        el.innerHTML = html;
      });
    }
  });

  if (suppressedCount > 0) {
    const notice  = document.createElement('span');
    notice.className = 'suppressed-notice';
    notice.textContent = `${suppressedCount} suppressed item${suppressedCount > 1 ? 's' : ''} — click to show`;
    let revealed = false;
    notice.addEventListener('click', () => {
      revealed = !revealed;
      list.querySelectorAll('.card--suppressed').forEach(c => {
        c.style.display = revealed ? '' : 'none';
        if (revealed) c.classList.remove('card--suppressed');
      });
      notice.textContent = revealed
        ? `${suppressedCount} suppressed item${suppressedCount > 1 ? 's' : ''} — click to hide`
        : `${suppressedCount} suppressed item${suppressedCount > 1 ? 's' : ''} — click to show`;
    });
    list.insertBefore(notice, list.firstChild);
  }
}

// ── Keyboard triage shortcuts ─────────────────────────────────────────────────
// Hover a card to focus it. Then: F = flag, I = interesting, R = read, Del = delete
function setupKeyboardTriage() {
  const list = document.getElementById('article-list');
  if (!list) return;

  let focused = null;

  list.addEventListener('mouseover', e => {
    const card = e.target.closest('.card');
    if (!card) return;
    if (focused) focused.classList.remove('card-focused');
    focused = card;
    focused.classList.add('card-focused');
  });

  document.addEventListener('keydown', e => {
    if (!focused || e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    const id = focused.dataset.id;
    if (!id) return;

    const actions = { f: 'flag', i: 'interesting', r: 'read', Delete: 'delete' };
    const act = actions[e.key];
    if (!act) return;

    e.preventDefault();
    fetch(`/action/${id}/${act}`, { method: 'POST' }).then(() => {
      focused.style.transition = 'opacity 0.15s, transform 0.15s';
      focused.style.opacity    = '0';
      focused.style.transform  = 'translateX(6px)';
      setTimeout(() => {
        focused?.remove();
        focused = null;
      }, 160);
    });
  });
}
