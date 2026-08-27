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

  const isFui    = document.documentElement.dataset.theme === 'fui';
  const isRiver  = window.location.pathname === '/river';

  // Touch session — record that the river was opened
  if (isRiver && !isFui && document.getElementById('article-list')) {
    setTimeout(() => fetch('/touch-session', { method: 'POST' }).catch(() => {}), 500);
  }

  if (isFui && isRiver) {
    setupFuiPanel();
    startGlitchEffects();
  } else {
    applyKeywordFilters();
    setupKeyboardTriage();
  }
});

// ── FUI split-panel ──────────────────────────────────────────────────────────

let _fuiArticles = [];
let _fuiActive   = null;

function setupFuiPanel() {
  const dataEl = document.getElementById('fui-data');
  if (!dataEl) return;
  _fuiArticles = JSON.parse(dataEl.textContent || '[]');

  const list = document.getElementById('fui-index-list');
  if (!list) return;

  // Select first row on load
  const firstRow = list.querySelector('.fui-index-row');
  if (firstRow) _fuiSelectRow(firstRow);

  list.addEventListener('click', e => {
    const row = e.target.closest('.fui-index-row');
    if (row) _fuiSelectRow(row);
  });

  // Keyboard: F/I/R/Delete acts on active article
  document.addEventListener('keydown', e => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || !_fuiActive) return;
    const map = { f: 'flag', i: 'interesting', r: 'read', Delete: 'delete' };
    const act = map[e.key];
    if (!act) return;
    e.preventDefault();
    _fuiTriage(_fuiActive, act);
  });

  // Touch session
  setTimeout(() => fetch('/touch-session', { method: 'POST' }).catch(() => {}), 500);
}

function _fuiSelectRow(row) {
  document.querySelectorAll('.fui-index-row').forEach(r => r.classList.remove('fui-row-active'));
  row.classList.add('fui-row-active');
  _fuiActive = row;

  const idx = parseInt(row.dataset.idx);
  const a   = _fuiArticles[idx];
  if (!a) return;

  const idEl = document.getElementById('fui-detail-id');
  if (idEl) idEl.textContent = `[ REC:0x${a.id.toString(16).toUpperCase().padStart(6,'0')} ]`;

  const scroll = document.getElementById('fui-detail-scroll');
  if (!scroll) return;

  const typeStr   = (a.content_type || 'ARTICLE').toUpperCase();
  const langStr   = (a.language || 'EN').toUpperCase();
  const srcStr    = (a.source   || 'UNKNOWN').toUpperCase().slice(0, 24);
  const dateStr   = a.date_published ? a.date_published.slice(0, 10) : '????-??-??';
  const doiStr    = a.doi ? a.doi.slice(0, 40) : 'NULL';
  const fetchHex  = a.id ? `0x${(a.id * 0x4F3D).toString(16).toUpperCase().slice(-6)}` : '0x??????';

  const titleHtml = a.url
    ? `<a href="${_esc(a.url)}" target="_blank" rel="noopener noreferrer">${_esc(a.title)}</a>`
    : _esc(a.title);

  const authorsHtml = a.authors
    ? `${_esc(a.authors)}${a.journal ? ' // <em>' + _esc(a.journal) + '</em>' : ''}`
    : '';

  const abstractHtml = a.abstract
    ? _esc(a.abstract)
    : null;

  scroll.innerHTML = `
    <div class="fui-kv-block">
      <span class="fui-k">ID</span>      <span class="fui-v fui-v-bright">0x${a.id.toString(16).toUpperCase().padStart(8,'0')}</span>
      <span class="fui-k">TYPE</span>    <span class="fui-v">${typeStr}</span>
      <span class="fui-k">LANG</span>    <span class="fui-v">${langStr}</span>
      <span class="fui-k">DATE</span>    <span class="fui-v">${dateStr}</span>
      <span class="fui-k">SOURCE</span>  <span class="fui-v">${srcStr}</span>
      <span class="fui-k">STATUS</span>  <span class="fui-v fui-v-bright">UNREAD</span>
      <span class="fui-k">DOI</span>     <span class="fui-v">${doiStr}</span>
      <span class="fui-k">CHKSUM</span>  <span class="fui-v">${fetchHex}</span>
    </div>
    <div class="fui-detail-title">${titleHtml}</div>
    ${authorsHtml ? `<div class="fui-detail-authors">${authorsHtml}</div>` : ''}
    ${abstractHtml
      ? `<div class="fui-detail-abstract">${abstractHtml}</div>`
      : '<div class="fui-no-abstract">NO ABSTRACT IN RECORD</div>'}
    <div class="fui-detail-actions" id="fui-actions-${a.id}">
      <button class="btn btn-flag"   data-fui-action="flag"        data-fui-id="${a.id}">★ FLAG</button>
      <button class="btn"            data-fui-action="interesting"  data-fui-id="${a.id}">INTERESTING</button>
      <button class="btn btn-read"   data-fui-action="read"         data-fui-id="${a.id}">✓ READ</button>
      <button class="btn btn-delete" data-fui-action="delete"       data-fui-id="${a.id}">✕ PURGE</button>
    </div>
  `;

  // Bind action buttons
  scroll.querySelectorAll('[data-fui-action]').forEach(b => {
    b.addEventListener('click', () => _fuiTriage(_fuiActive, b.dataset.fuiAction));
  });
}

function _fuiTriage(row, action) {
  if (!row) return;
  const id = row.dataset.id;
  fetch(`/action/${id}/${action}`, { method: 'POST' }).then(() => {
    row.style.transition = 'opacity 0.15s, transform 0.15s';
    row.style.opacity    = '0';
    row.style.transform  = 'translateX(8px)';
    setTimeout(() => {
      const next = row.nextElementSibling?.classList.contains('fui-index-row')
        ? row.nextElementSibling
        : row.previousElementSibling?.classList.contains('fui-index-row')
          ? row.previousElementSibling
          : null;
      row.remove();
      // Remove from data array
      const idx = parseInt(row.dataset.idx);
      _fuiArticles.splice(idx, 1);
      // Re-index remaining rows
      document.querySelectorAll('.fui-index-row').forEach((r, i) => r.dataset.idx = i);
      if (next) _fuiSelectRow(next);
      else {
        const scroll = document.getElementById('fui-detail-scroll');
        if (scroll) scroll.innerHTML = '<div class="fui-detail-empty">BUFFER EMPTY</div>';
        const idEl = document.getElementById('fui-detail-id');
        if (idEl) idEl.textContent = '[ -- ]';
        _fuiActive = null;
      }
    }, 160);
  });
}

function _esc(s) {
  if (!s) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function startGlitchEffects() {
  function doGlitch() {
    const rows = document.querySelectorAll('.fui-index-row');
    if (rows.length) {
      const r = rows[Math.floor(Math.random() * rows.length)];
      r.classList.add('fui-row-glitch');
      setTimeout(() => r.classList.remove('fui-row-glitch'), 150);
    }
    setTimeout(doGlitch, 3500 + Math.random() * 9000);
  }
  setTimeout(doGlitch, 1500 + Math.random() * 2000);
}

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
