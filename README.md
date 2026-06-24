# Campaign Brief Generator

A full-stack Flask web app that uses the **Anthropic Claude API** to generate complete marketing campaign briefs for nonprofits and social-impact organisations — with live streaming, audience personas, visual suggestions, saved history, an organisations library, and one-click PDF export.

Built by **Chelsi Patel**.

---

## ✨ Features

- **AI-generated campaign briefs** — enter an organisation, cause, audience, tone, goal and target platforms, and the app generates a full brief using Claude, **streamed live** to the browser token-by-token.
- **Audience personas** — generates target-audience personas to sharpen campaign focus.
- **Content & visual suggestions** — proposes post ideas and visual direction per platform.
- **Refine / tweak** — iterate on a generated brief with follow-up instructions.
- **Saved history** — briefs are stored in a database and can be revisited or deleted.
- **Organisations library** — full CRUD for reusable org profiles (mission, brand voice, audience, past campaigns).
- **PDF export** — download a cleanly formatted, branded campaign brief as a PDF.

## 🛠️ Tech stack

| Layer | Technology |
|-------|------------|
| Backend | Python, Flask |
| AI | Anthropic Claude API (`anthropic` SDK) with streaming |
| Database | SQLite |
| PDF | `fpdf` |
| Frontend | HTML, CSS, JavaScript (server-rendered templates) |
| Deployment | Railway (`Procfile`, `railway.json`) |

## 🚀 Getting started

### Prerequisites
- Python 3.11+
- An Anthropic API key

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set your API key
The app reads the key from the `ANTHROPIC_API_KEY` environment variable.

```bash
# macOS / Linux
export ANTHROPIC_API_KEY="your-key-here"

# Windows (PowerShell)
$env:ANTHROPIC_API_KEY = "your-key-here"
```

### 3. Run the app
```bash
python app.py
```
Then open **http://localhost:5000** in your browser. The SQLite database is created automatically on first run.

## 📂 Project structure

```
campaign-brief-generator/
├── app.py              # Flask backend: routes, Claude calls (streaming), PDF export
├── database.py         # SQLite connection + schema (briefs, orgs)
├── models/
│   └── brief.py        # Brief data-access layer (save / list / get / delete)
├── templates/
│   ├── index.html      # Main UI
│   └── orgs.html       # Organisations management UI
├── static/             # CSS + JS
├── requirements.txt
├── Procfile            # Railway/Gunicorn entry point
└── railway.json        # Railway deployment config
```

## 🔌 Key endpoints

| Route | Method | Purpose |
|-------|--------|---------|
| `/` | GET | Main app UI |
| `/generate` | POST | Generate a campaign brief (streamed) |
| `/personas` | POST | Generate audience personas |
| `/suggestions` | POST | Content suggestions |
| `/visuals` | POST | Visual direction suggestions |
| `/tweak` | POST | Refine an existing brief |
| `/save` · `/history` | POST · GET | Save and list briefs |
| `/orgs` | GET/POST/PUT/DELETE | Manage organisation profiles |
| `/export/pdf` | POST | Export a brief to PDF |

## 🔒 Notes
- No secrets are committed — the API key is supplied via environment variable only.
- The local database (`briefs.db`), logs, and caches are excluded via `.gitignore`.
