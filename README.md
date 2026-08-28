# RSS Feed Dashboard with CyberDeck aesthetic 

A desktop app for tracking research papers, RSS feeds, and academic sources. Runs as a native window powered by Flask + pywebview.

---

## Install

### Requirements

- Python 3.10 or newer
- pip

---

### macOS

```bash
# 1. Clone the repo
git clone https://github.com/skohnbohn/surrealism-papers-dashboard.git
cd surrealism-papers-dashboard

# 2. Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run
python3 main.py
```

---

### Windows

```bash
# 1. Clone the repo
git clone https://github.com/skohnbohn/surrealism-papers-dashboard.git
cd surrealism-papers-dashboard

# 2. Create a virtual environment
python -m venv .venv
.venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
pip install pywebview[winforms]

# 4. Run
python main.py
```

> Windows needs `pywebview[winforms]` for the native window backend.  
> Make sure [Microsoft Edge WebView2](https://developer.microsoft.com/en-us/microsoft-edge/webview2/) is installed — it ships with Windows 11 and most updated Windows 10 installs.

---

### Linux

```bash
# 1. Install system dependencies (Ubuntu/Debian)
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.0

# 2. Clone the repo
git clone https://github.com/skohnbohn/surrealism-papers-dashboard.git
cd surrealism-papers-dashboard

# 3. Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt
pip install pywebview[gtk]

# 5. Run
python3 main.py
```

> On Arch: install `python-gobject`, `webkit2gtk` via pacman instead of the apt packages above.

---

## First run

The app opens a native window. On first launch:

1. Go to **Settings → SRC_REGISTRY** and add your RSS/Atom feeds or academic sources
2. Go to **Settings → QUERY_VECTORS** to set your OpenAlex and BASE search terms
3. Hit **SYNC_INIT** in the sidebar to fetch — results appear in the **River** view

The database (`surrealism.db`) is created automatically in the project folder on first run.

---

## Notes

- No internet connection is needed after install except for fetching feeds
- The UI fonts (VT323, Share Tech Mono) load from Google Fonts — if you're offline they fall back to system monospace, which looks different but doesn't break anything
- Data is stored locally in SQLite — nothing is sent anywhere
