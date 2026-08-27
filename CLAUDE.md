# Sky — CLAUDE.md

## What this is
Flask + SQLite desktop app wrapped in **pywebview** (WKWebView on macOS). Not a browser app — runs via `python3 main.py`. Server on `127.0.0.1:5000`, pywebview displays it natively.

## Dev branch
`anti-attention-economy-social-media-feed`

## Key files
| File | Role |
|---|---|
| `app.py` | Flask routes, SQLite, APScheduler fetch |
| `main.py` | pywebview entry point (`easy_drag=False` required for text selection on macOS) |
| `static/style.css` | Classic yellow theme — base font `html { font-size: 20px }` (line 11), all sizes in `rem` |
| `static/style-fui.css` | FUI lavender phosphor theme — sizes in `px`, ~1380 lines |
| `static/app.js` | All JS: HTMX replacement, FUI panel logic, keyboard nav, ambient animations |
| `templates/base.html` | Sidebar, nav, clock/uptime strip (shared), ticker+dossier (FUI only) |
| `templates/river.html` | River view — FUI split-panel branch + classic card-list branch |

## Theme system
`<html data-theme="fui">` activates FUI. Classic is default (no attribute).
Both stylesheets always load. FUI rules are scoped to `[data-theme="fui"]`.
Toggle saved server-side via `/settings`.

## FUI flex layout — CRITICAL
Do not use `zoom` on the root — it inflates `flex-shrink: 0` elements and pushes bottom panels off-screen.

```
body (flex row, h:100vh, overflow:hidden)
├── .sidebar (flex col, 250px, overflow:hidden)
│   ├── .sidebar-top        — app name, clock/uptime
│   ├── .sidebar-nav        — flex:1
│   ├── .fui-ticker         — flex-shrink:0  ← bottom ambient, clips if sidebar too full
│   ├── .fui-dossier        — flex-shrink:0  ← x-ray image panel
│   └── .sidebar-bottom     — flex-shrink:0  — fetch button
└── .main (flex col, flex:1, overflow:hidden)
    └── .fui-river-wrapper (flex row, flex:1, overflow:hidden)
        ├── .fui-index-panel (flex col, 40%/320px min, overflow:hidden)
        │   ├── .fui-panel-hdr   — flex-shrink:0
        │   ├── .fui-index-list  — flex:1, overflow-y:auto
        │   └── .fui-scan-beam   — absolute, animated CRT beam
        └── .fui-detail-panel (flex col, flex:1, overflow:hidden)
            ├── .fui-panel-hdr     — flex-shrink:0
            ├── .fui-detail-scroll — flex:1, min-height:0 ← REQUIRED or instruments get pushed off
            ├── .fui-instruments   — flex-shrink:0  ← signal bars + waveform + stats
            └── .fui-syslog        — flex-shrink:0  ← live log lines
```

**Rule**: if bottom panels disappear, check `min-height: 0` on `.fui-detail-scroll` and `.fui-index-list`. Default `min-height: auto` breaks layout when content is tall.

## FUI CSS line reference (style-fui.css)
| Element | Line | Key property |
|---|---|---|
| Token palette (`--p0`–`--p7`) | 72 | Colors + fonts |
| `.sidebar` | 142 | width: 250px |
| `.nav-item` | 222 | font-size: 15px |
| `.fui-panel-hdr` | 385 | font-size: 12px |
| `.fui-index-panel` | 347 | min-width: 320px |
| `.fui-index-row` | 434 | padding, row height |
| `.fui-row-title` | 493 | font-size: 15px |
| `.fui-detail-scroll` | 540 | flex:1, min-height:0 |
| `.fui-kv-block` | 580 | font-size: 14px |
| `.fui-detail-title` | 605 | font-size: 24px |
| `.fui-detail-abstract` | 629 | font-size: 17px |
| `.fui-instruments` | 699 | signal bars + waveform strip |
| `.fui-dossier` | 1174 | x-ray sidebar image |
| `.fui-syslog` | 1292 | live log strip |
| `.fui-ticker` | 1327 | scrolling hex ticker |

## Classic CSS line reference (style.css)
| Element | Line |
|---|---|
| `html` font-size (20px) | 11 |
| `.sidebar` (270px) | 32 |
| `.nav-item` | 66 |
| `.card` | 198 |
| `.card-title` | 230 |
| `.card-abstract` | 262 |
| `.btn` | 278 |

## JS architecture (app.js)
- `setupFuiPanel()` — called on river page load; wires index row clicks, keyboard nav (↑↓ arrows, Enter, F/I/R/Del)
- `_fuiSelectRow(row)` — selects a row, shows verify flash, renders article detail via `fui-data` JSON
- `_fuiTriage(row, action)` — POSTs flag/interesting/read/delete, removes row from index
- `startFuiClock()` — updates `#fui-clock` + `#fui-uptime` every second (unconditional, self-guards on element)
- `startRecvCounter()` — increments `#fui-recv-count` hex badge (unconditional)
- `startSyslog()` — adds fake log lines to `#fui-syslog-lines` every 2.8–7.3s (unconditional)
- `setupKeyboardTriage()` — classic theme card keyboard nav

Auto-adopt pattern: ambient functions guard on `document.getElementById()` and are called unconditionally in `DOMContentLoaded`. Adding an element to either theme automatically activates it.

## Static assets
- `fui-dossier.jpg` — x-ray spine scan (sidebar dossier, CSS filter shifts to lavender)
- `fui-texture-index.jpg` — holographic hands (index panel bg, 5.5% opacity, screen blend)
- `fui-texture-detail.jpg` — pixelated flower (detail panel bg, 5% opacity, screen blend)

## pywebview notes
- macOS: `easy_drag=False` in `main.py` — required for text selection (drag gesture conflicts)
- Text selection: `-webkit-user-select: text` on `*` in both stylesheets
- `::selection` styled: FUI = lavender (`--p1` bg / `--p7` text), Classic = black bg / yellow text
- No CDN — fully offline. No external fetch in JS.
