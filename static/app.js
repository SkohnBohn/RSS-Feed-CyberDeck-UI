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
    startSysMetrics();
  } else {
    applyKeywordFilters();
    setupKeyboardTriage();
  }

  // Shared ambient — element-guarded; auto-activates in whichever theme has the DOM element
  startFuiClock();
  startRecvCounter();
  startSyslog();
});

// ── FUI split-panel ──────────────────────────────────────────────────────────

let _fuiArticles = [];
let _fuiActive   = null;
let _fuiSelectGen = 0;

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

  // Arrow keys navigate index rows; F/I/R/Del triage active article
  document.addEventListener('keydown', e => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      const rows = [...document.querySelectorAll('.fui-index-row')];
      if (!rows.length) return;
      const ci = _fuiActive ? rows.indexOf(_fuiActive) : -1;
      const ni = Math.max(0, Math.min(rows.length - 1, ci + (e.key === 'ArrowDown' ? 1 : -1)));
      if (rows[ni] && rows[ni] !== _fuiActive) {
        _fuiSelectRow(rows[ni]);
        rows[ni].scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
      return;
    }
    if (!_fuiActive) return;
    const map = { f: 'flag', i: 'interesting', r: 'read', Delete: 'delete' };
    const act = map[e.key];
    if (!act) return;
    e.preventDefault();
    _fuiTriage(_fuiActive, act);
  });

  // Touch session
  setTimeout(() => fetch('/touch-session', { method: 'POST' }).catch(() => {}), 500);
}

// ── Live clock + session uptime ───────────────────────────────────────────────
function startFuiClock() {
  const clockEl  = document.getElementById('fui-clock');
  const uptimeEl = document.getElementById('fui-uptime');
  if (!clockEl && !uptimeEl) return;
  const t0 = Date.now();
  function tick() {
    const now = new Date();
    if (clockEl) clockEl.textContent = now.toTimeString().slice(0, 8);
    if (uptimeEl) {
      const s   = Math.floor((Date.now() - t0) / 1000);
      const hh  = String(Math.floor(s / 3600)).padStart(2, '0');
      const mm  = String(Math.floor((s % 3600) / 60)).padStart(2, '0');
      const ss  = String(s % 60).padStart(2, '0');
      uptimeEl.textContent = `${hh}:${mm}:${ss}`;
    }
  }
  tick();
  setInterval(tick, 1000);
}

// ── RECV counter ──────────────────────────────────────────────────────────────
function startRecvCounter() {
  const el = document.getElementById('fui-recv-count');
  if (!el) return;
  let val = Math.floor(Math.random() * 0xFFFF);
  function bump() {
    val = (val + Math.floor(Math.random() * 0x1FF + 1)) & 0xFFFF;
    el.textContent = `RCV:0x${val.toString(16).toUpperCase().padStart(4, '0')}`;
    setTimeout(bump, 1600 + Math.random() * 2800);
  }
  setTimeout(bump, 800 + Math.random() * 1200);
}

// ── System log ────────────────────────────────────────────────────────────────
const _syslogMessages = [
  'LINK HEARTBEAT OK',
  'PKT RECV · ACK SENT',
  'AUTH TOKEN REFRESHED',
  'BUFFER FLUSH COMPLETE',
  'CHECKSUM VERIFIED',
  'INDEX REBUILT',
  'CONN TIMEOUT · RETRY 1/3',
  'CONN RESTORED · STABLE',
  'CACHE HIT RATIO: 94%',
  'SYNC PULSE NOMINAL',
  'COMPRESSION RATIO 3.2:1',
  'THREAD POOL NOMINAL',
  'HEAP ALLOCATION OK',
  'RECV 0xA21E · DECRYPTED',
  'UPLINK SIGNAL +82%',
  'SECTOR SCAN COMPLETE',
];

function startSyslog() {
  const container = document.getElementById('fui-syslog-lines');
  if (!container) return;
  function addLine() {
    const msg = _syslogMessages[Math.floor(Math.random() * _syslogMessages.length)];
    const div = document.createElement('div');
    div.className = 'fui-syslog-line fui-sl-bright';
    div.textContent = msg;
    container.appendChild(div);
    // Age out older lines
    const lines = container.querySelectorAll('.fui-syslog-line');
    lines.forEach((l, i) => {
      if (i < lines.length - 1) {
        l.classList.remove('fui-sl-bright');
        l.classList.add('fui-sl-dim');
      }
    });
    while (container.children.length > 4) container.removeChild(container.firstChild);
    setTimeout(addLine, 2800 + Math.random() * 4500);
  }
  setTimeout(addLine, 1500);
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

  const gen = ++_fuiSelectGen;

  // Verifying flash
  scroll.innerHTML = '<div class="fui-detail-verify">VERIFYING RECORD · CHECKSUM…</div>';

  setTimeout(() => {
    if (_fuiSelectGen !== gen) return;
    scroll.innerHTML = '<div class="fui-detail-verify fui-verify-ok">CRC OK · DECRYPTING RECORD</div>';

    setTimeout(() => {
      if (_fuiSelectGen !== gen) return;

      const typeStr  = (a.content_type || 'ARTICLE').toUpperCase();
      const langStr  = (a.language || 'EN').toUpperCase();
      const srcStr   = (a.source   || 'UNKNOWN').toUpperCase().slice(0, 24);
      const dateStr  = a.date_published ? a.date_published.slice(0, 10) : '????-??-??';
      const doiStr   = a.doi ? a.doi.slice(0, 40) : 'NULL';
      const fetchHex = a.id ? `0x${(a.id * 0x4F3D).toString(16).toUpperCase().slice(-6)}` : '0x??????';

      const titleHtml = a.url
        ? `<a href="${_esc(a.url)}" target="_blank" rel="noopener noreferrer">${_esc(a.title)}</a>`
        : _esc(a.title);

      const authorsHtml = a.authors
        ? `${_esc(a.authors)}${a.journal ? ' // <em>' + _esc(a.journal) + '</em>' : ''}`
        : '';

      const abstractHtml = a.abstract ? _esc(a.abstract) : null;

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

      scroll.querySelectorAll('[data-fui-action]').forEach(b => {
        b.addEventListener('click', () => _fuiTriage(_fuiActive, b.dataset.fuiAction));
      });

      // Log the record load
      const logEl = document.getElementById('fui-syslog-lines');
      if (logEl) {
        const div = document.createElement('div');
        div.className = 'fui-syslog-line fui-sl-bright';
        div.textContent = `RECORD 0x${a.id.toString(16).toUpperCase().padStart(4,'0')} LOADED`;
        logEl.appendChild(div);
        logEl.querySelectorAll('.fui-syslog-line').forEach((l, i, arr) => {
          if (i < arr.length - 1) { l.classList.remove('fui-sl-bright'); l.classList.add('fui-sl-dim'); }
        });
        while (logEl.children.length > 4) logEl.removeChild(logEl.firstChild);
      }
    }, 160);
  }, 290);
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
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  function doGlitch() {
    const rows = document.querySelectorAll('.fui-index-row');
    if (rows.length) {
      const r = rows[Math.floor(Math.random() * rows.length)];
      r.classList.add('fui-row-glitch');
      setTimeout(() => r.classList.remove('fui-row-glitch'), 130);
    }
    // Prime numbers prevent lockstep with flicker (7s) and scanBeam (5.3s)
    setTimeout(doGlitch, 4700 + Math.random() * 8300);
  }
  setTimeout(doGlitch, 2300 + Math.random() * 1800);
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

// ── Live system metrics (CPU waveform + core bars + net stats) ───────────────
function startSysMetrics() {
  const canvas = document.getElementById('fui-waveform-canvas');
  if (!canvas) return;

  const cpuHistory = new Array(80).fill(0);
  let animFrame = null;

  function fmtBps(bps) {
    if (bps < 1024)       return `${Math.round(bps)}B/s`;
    if (bps < 1048576)    return `${(bps / 1024).toFixed(1)}K/s`;
    return `${(bps / 1048576).toFixed(1)}M/s`;
  }

  function drawWaveform(ctx, w, h) {
    ctx.clearRect(0, 0, w, h);

    const pts = cpuHistory.length;
    const stepX = w / (pts - 1);

    // Grid lines at 25%, 50%, 75%
    ctx.strokeStyle = 'rgba(180,184,255,0.08)';
    ctx.lineWidth = 1;
    [0.25, 0.5, 0.75].forEach(f => {
      const y = h - f * h;
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
    });

    // Filled area under curve
    ctx.beginPath();
    cpuHistory.forEach((v, i) => {
      const x = i * stepX;
      const y = h - (v / 100) * h;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.lineTo((pts - 1) * stepX, h);
    ctx.lineTo(0, h);
    ctx.closePath();
    ctx.fillStyle = 'rgba(180,184,255,0.07)';
    ctx.fill();

    // Main line
    ctx.beginPath();
    cpuHistory.forEach((v, i) => {
      const x = i * stepX;
      const y = h - (v / 100) * h;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.strokeStyle = 'rgba(200,204,255,0.85)';
    ctx.lineWidth = 1.5;
    ctx.shadowColor = 'rgba(180,184,255,0.6)';
    ctx.shadowBlur = 4;
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Leading dot
    const lx = (pts - 1) * stepX;
    const ly = h - (cpuHistory[pts - 1] / 100) * h;
    ctx.beginPath();
    ctx.arc(lx, ly, 2.5, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(220,224,255,1)';
    ctx.shadowColor = 'rgba(180,184,255,0.9)';
    ctx.shadowBlur = 8;
    ctx.fill();
    ctx.shadowBlur = 0;
  }

  function renderCanvas() {
    const dpr = window.devicePixelRatio || 1;
    const w   = canvas.clientWidth;
    const h   = canvas.clientHeight || 36;
    if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
      canvas.width  = w * dpr;
      canvas.height = h * dpr;
    }
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    drawWaveform(ctx, w, h);
  }

  function updateBars(cores) {
    const bars = document.querySelectorAll('.fui-sbar');
    bars.forEach((bar, i) => {
      const pct = cores.length > 0 ? cores[i % cores.length] : 0;
      const px  = Math.max(2, Math.round((pct / 100) * 28));
      bar.style.height  = px + 'px';
      bar.style.opacity = 0.35 + (pct / 100) * 0.65;
    });
  }

  async function poll() {
    try {
      const d = await fetch('/api/sysmetrics').then(r => r.json());

      cpuHistory.push(d.cpu);
      if (cpuHistory.length > 80) cpuHistory.shift();

      if (animFrame) cancelAnimationFrame(animFrame);
      animFrame = requestAnimationFrame(renderCanvas);

      updateBars(d.cpu_cores);

      const cpuEl = document.getElementById('fui-cpu-pct');
      const memEl = document.getElementById('fui-mem-pct');
      const upEl  = document.getElementById('fui-net-up');
      const dnEl  = document.getElementById('fui-net-dn');
      if (cpuEl) cpuEl.textContent = d.cpu.toFixed(1);
      if (memEl) memEl.textContent = d.mem.toFixed(1);
      if (upEl)  upEl.textContent  = fmtBps(d.net_sent_bps);
      if (dnEl)  dnEl.textContent  = fmtBps(d.net_recv_bps);
    } catch (_) {}
    setTimeout(poll, 900);
  }

  // Initial draw with zeros, then start polling
  renderCanvas();
  setTimeout(poll, 300);
}

// ── Keyboard triage shortcuts ─────────────────────────────────────────────────
// Arrow keys navigate cards. F/I/R/Del triage focused card. Enter opens article.
function setupKeyboardTriage() {
  const list = document.getElementById('article-list');
  if (!list) return;

  let focused = null;

  function focusCard(card) {
    if (focused) focused.classList.remove('card-focused');
    focused = card;
    if (focused) {
      focused.classList.add('card-focused');
      focused.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }

  function moveCard(delta) {
    const cards = [...list.querySelectorAll('.card:not(.card--suppressed)')];
    const ci    = focused ? cards.indexOf(focused) : -1;
    const ni    = Math.max(0, Math.min(cards.length - 1, ci + delta));
    if (cards[ni]) focusCard(cards[ni]);
  }

  list.addEventListener('mouseover', e => {
    const card = e.target.closest('.card');
    if (card) focusCard(card);
  });

  document.addEventListener('keydown', e => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    if (e.key === 'ArrowDown') { e.preventDefault(); moveCard(1);  return; }
    if (e.key === 'ArrowUp')   { e.preventDefault(); moveCard(-1); return; }

    if (e.key === 'Enter' && focused) {
      e.preventDefault();
      const link = focused.querySelector('a.card-title');
      if (link) window.open(link.href, '_blank', 'noopener,noreferrer');
      return;
    }

    if (!focused) return;
    const id = focused.dataset.id;
    if (!id) return;

    const actions = { f: 'flag', i: 'interesting', r: 'read', Delete: 'delete' };
    const act = actions[e.key];
    if (!act) return;

    e.preventDefault();
    fetch(`/action/${id}/${act}`, { method: 'POST' }).then(() => {
      const next = focused.nextElementSibling?.closest?.('.card') || focused.previousElementSibling?.closest?.('.card');
      focused.style.transition = 'opacity 0.15s, transform 0.15s';
      focused.style.opacity    = '0';
      focused.style.transform  = 'translateX(6px)';
      setTimeout(() => {
        focused?.remove();
        focused = null;
        if (next) focusCard(next);
      }, 160);
    });
  });
}
