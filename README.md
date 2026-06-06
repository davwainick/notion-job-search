# notion-job-search

> **Scaffold a job-search CRM workspace in Notion — four linked databases,
> a Gap Analysis page, and optional seed data, all built from a single
> command or one click.**

---

## Table of Contents

- [Downloading the Executable](#downloading-the-executable)
- [GUI Usage](#gui-usage)
- [Building the Executable Yourself](#building-the-executable-yourself)
- [CLI Usage](#cli-usage)
- [Prerequisites](#prerequisites)
- [Setup (CLI)](#setup-cli)
- [CLI Reference](#cli-reference)
- [Running the Tests](#running-the-tests)
- [Why It's Technically Interesting](#why-its-technically-interesting)
- [Project Structure](#project-structure)
- [Design Decisions](#design-decisions)
- [License](#license)

---

## Downloading the Executable

Pre-built binaries for **Windows**, **macOS**, and **Linux** are attached to
every release on the GitHub Releases page.  No Python installation required.

👉 **[Download from Releases](https://github.com/davwainick/notion-job-search/releases)**

| Platform | File |
|----------|------|
| Windows | `NotionJobSearch-windows.exe` |
| macOS   | `NotionJobSearch-macos` |
| Linux   | `NotionJobSearch-linux` |

The executables are built automatically by GitHub Actions on every release —
see [`.github/workflows/build.yml`](.github/workflows/build.yml).

---

## GUI Usage

### Screen 1 — Setup (first run)

On first launch the app shows a setup form:

1. **Notion Integration Token** — paste your `secret_` token
   (click the *How do I get this?* link if you need one)
2. **Parent Page ID** — the ID from your Notion page's URL
3. **Workspace Name** — what to call the page in Notion (default: `Job Search HQ`)
4. Optionally check **Add 3 sample company rows**
5. Click **Create Workspace**

A live progress indicator updates through each of the 5 build steps.
If anything fails, the error is shown in red and the button re-enables
so you can try again.

### Screen 2 — Gap Analysis input

After the workspace is built you are taken to the Gap Analysis screen.
Here you can:

- Add **Strengths** — each with a talking point for interviews
- Add **Gaps / Objections** — each with a rebuttal and mitigation strategy

Click **Save & Open Notion** to write your content to the Gap Analysis page
and open Notion in your browser, or **Skip** to fill it in later directly
in Notion.

### Screen 3 — Returning user

On subsequent launches the app shows a list of your previously created
workspaces.  From here you can:

- **Open in Notion** — jump straight to the workspace
- **Create New Workspace** — go back to the setup form
- **Delete** — remove an entry from the local list (does not delete anything in Notion)

Your integration token is encrypted and stored locally at
`~/.notion_job_search/workspaces.json`.

---

## Building the Executable Yourself

```bash
# Install build dependencies
pip install pyinstaller notion-client python-dotenv cryptography

# Run the build script from the project root
python build.py
```

The output is placed in `dist/`:
- Windows: `dist/NotionJobSearch.exe`
- macOS / Linux: `dist/NotionJobSearch`

Do **not** commit the `dist/` or `build/` directories — they are in `.gitignore`.

---

## CLI Usage

If you prefer the command line, no GUI is needed:

```bash
# Copy .env.example to .env and fill in your token and page ID
cp .env.example .env

# Preview what would be created (no API calls)
python -m notion_job_search --dry-run

# Build the workspace
python -m notion_job_search

# Custom name + seed data
python -m notion_job_search --name "My 2025 Job Hunt" --seed-data

# Verbose output
python -m notion_job_search --seed-data --verbose
```

The CLI creates the Gap Analysis page with instructional placeholder text.
Fill it in directly in Notion or use the GUI.

---

## Prerequisites

- Python 3.10+ (CLI / build only — the executable is standalone)
- A free [Notion](https://notion.so) account
- A Notion Internal Integration token
- An existing Notion page to use as the workspace parent

---

## Setup (CLI)

### 1. Clone and install

```bash
git clone https://github.com/YOURUSERNAME/notion-job-search.git
cd notion-job-search
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Create a Notion integration

1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Click **+ New integration**, name it, copy the token (`secret_…`)

### 3. Connect it to a page

1. Open your root Notion page → `···` menu → **Connections** → select your integration
2. Copy the page ID from the URL:
   `notion.so/workspace/`**`1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d`**

### 4. Configure `.env`

```bash
cp .env.example .env
# Edit .env: fill in NOTION_TOKEN and NOTION_PARENT_PAGE_ID
```

---

## CLI Reference

```
usage: notion-job-search [-h] [--dry-run] [--seed-data]
                          [--name NAME] [--token TOKEN]
                          [--parent PAGE_ID] [--verbose]

options:
  --dry-run        Simulate all operations, print payloads, no API calls
  --seed-data      Insert 3 generic placeholder company rows
  --name NAME      Workspace name (default: "Job Search HQ")
  --token TOKEN    Notion token (overrides NOTION_TOKEN env var)
  --parent PAGE_ID Parent page ID (overrides NOTION_PARENT_PAGE_ID)
  --verbose        DEBUG-level logging
```

---

## Running the Tests

The full test suite runs offline — no Notion account needed.

```bash
pytest tests/ -v
```

---

## Why It's Technically Interesting

### Two-pass API orchestration

Notion's relation properties require the *target* database to already exist.
The script handles this with a two-pass approach:

1. Create all four databases — collect their IDs from the API responses
2. Make a second round of `PATCH /v1/databases/{id}` calls to wire up the
   seven cross-database relations

This is a hard constraint of the Notion API that naive implementations miss.

### SDK `pick()` whitelist fix

The `notion-client` SDK's `databases.create()` and `databases.update()`
methods use an internal `pick()` function that whitelists only specific kwargs.
`properties` is **not** on that whitelist, so it is silently dropped —
causing Notion to return `body.properties should be defined, instead was undefined`.

The fix uses `client.request()` directly for those two calls:

```python
# Wrong — properties silently dropped by pick()
client.databases.create(parent=..., title=..., properties=schema)

# Correct — bypasses pick(), sends full body
client.request(path="databases", method="POST", body={
    "parent": ..., "title": ..., "properties": schema
})
```

### Separation of concerns

| Module | Responsibility |
|--------|----------------|
| `config.py` | All schema definitions and seed data — pure data, no API logic |
| `builder.py` | Orchestration — builds payloads, calls API in correct order |
| `client.py` | Network concerns — auth, version pin, error wrapping |
| `cli.py` | CLI interface — argparse, .env loading, exit codes |
| `gui.py` | GUI interface — Tkinter three-screen workflow |
| `state.py` | Persistence — encrypted local state file |

### Machine-local token encryption

The GUI stores the Notion integration token encrypted at rest using Fernet
symmetric encryption. A key is generated once at `~/.notion_job_search/.key`
and reused on subsequent runs — the token is never stored in plain text.

### GitHub Actions cross-platform builds

`.github/workflows/build.yml` builds Windows, macOS, and Linux executables
in parallel on every push to `main` and attaches them to GitHub Releases
automatically.

---

## Project Structure

```
notion-job-search/
│
├── notion_job_search/
│   ├── __init__.py
│   ├── __main__.py
│   ├── builder.py       — workspace orchestration
│   ├── cli.py           — command-line interface
│   ├── client.py        — Notion SDK wrapper + error handling
│   ├── config.py        — all schemas and seed data
│   ├── gui.py           — Tkinter GUI (three-screen workflow)
│   └── state.py         — encrypted local state file management
│
├── tests/
│   ├── __init__.py
│   ├── test_builder.py  — builder + config tests (offline)
│   └── test_state.py    — state file tests (offline, tmp_path)
│
├── .github/
│   └── workflows/
│       └── build.yml    — CI: builds Win/macOS/Linux executables
│
├── build.py             — PyInstaller build script
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
├── requirements.txt
└── setup.py
```

---

## Design Decisions

**Why `client.request()` instead of `client.databases.create()`?**
The SDK's convenience methods filter kwargs through a `pick()` whitelist.
`properties` is excluded, so it gets silently dropped. `client.request()`
bypasses this and sends whatever body you provide.

**Why Tkinter?**
Zero external GUI dependencies — Tkinter ships with Python on all platforms,
which keeps the executable size manageable and eliminates install friction.

**Why a machine-local key for encryption?**
Tying the key to a persistent file (rather than deriving from hostname or
hardware) means the key survives hostname changes and renames, while still
protecting the token from casual inspection of the JSON file.

**Why `--dry-run`?**
Lets the tool be tested in CI and demoed without a live Notion account.
Every payload that would be sent is printed in full.

---

## License

MIT — see [LICENSE](LICENSE).
