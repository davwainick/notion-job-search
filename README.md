# notion-job-search

> **Automatically scaffold a B2B-style job-search CRM in Notion — four linked
> databases, a gap analysis page, and seed data, all built from a single
> command.**

---

## Table of Contents

- [What This Project Does](#what-this-project-does)
- [Why It's Technically Interesting](#why-its-technically-interesting)
- [The Workspace It Builds](#the-workspace-it-builds)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Running the Script](#running-the-script)
- [CLI Reference](#cli-reference)
- [Running the Tests](#running-the-tests)
- [Design Decisions](#design-decisions)
- [Extending the Project](#extending-the-project)
- [License](#license)

---

## What This Project Does

`notion-job-search` is a Python package that calls the
[Notion API](https://developers.notion.com/) to programmatically create a
fully structured job-search workspace inside your Notion account.

Running one command builds:

- A parent page called **Job Search HQ**
- **Four linked databases** that mirror a B2B sales pipeline
  (Companies → Job Postings → Contacts → Outreach Log)
- All **cross-database relations** wired up automatically
- A **Gap Analysis** sub-page with pre-filled interview prep content
- Optionally, **five realistic seed rows** in the Companies database

The whole workspace is ready to use in under 60 seconds — no clicking through
Notion's UI, no copying templates, no manually setting up 60+ properties across
four databases.

---

## Why It's Technically Interesting

If you're a technical recruiter or hiring manager reviewing this project, here
is a quick summary of the engineering decisions that make it worth reading:

### 1. Real API orchestration with dependency ordering

Notion's relation properties require the *target* database to already exist
before you can create a property that points to it.  The script handles this
by:

1. Creating all four databases first (no relations).
2. Collecting their IDs from the API responses.
3. Making a second pass (`PATCH /v1/databases/{id}`) to wire up the seven
   cross-database relations.

This is a real constraint of the Notion API that trips up naive implementations.

### 2. Separation of concerns

The codebase is split into three distinct layers:

| Module | Responsibility |
|--------|----------------|
| `config.py` | **Schema definitions only** — all property declarations, seed data, and gap analysis content live here as pure data structures, completely separate from any API logic |
| `builder.py` | **Orchestration** — constructs payloads from config data and calls the API in the right order |
| `client.py` | **Network concerns** — auth, version pinning, and error wrapping |
| `cli.py` | **User interface** — `argparse`, `.env` loading, exit codes |

This structure means you can change a database schema by editing one dict in
`config.py` without touching any API code.

### 3. API version pinning

The Notion API introduced breaking changes in its September 2025 version.  All
requests in this project send the `Notion-Version: 2022-06-28` header
(configured once in `client.py`, applied to every request automatically via
the SDK), ensuring stability regardless of when the script is run.

### 4. Official SDK over raw requests

The project uses the official [`notion-client`](https://github.com/ramnes/notion-sdk-py)
Python SDK rather than `requests`.  The SDK provides:

- Automatic request retries on transient failures
- Typed `APIResponseError` exceptions with `.status`, `.code`, and `.message`
- Cleaner, more maintainable call syntax

### 5. Graceful error handling

Every API call is wrapped in `safe_api_call()`, which catches
`APIResponseError` and re-raises it as a `RuntimeError` with a human-readable
message that includes the HTTP status code, Notion's error code, and the
context of what was being attempted — so failures are debuggable without
reading the Notion API docs.

### 6. `--dry-run` mode

The `--dry-run` flag lets you preview exactly what *would* be sent to the API
(full JSON payloads, all seven relation patches, all seed rows) without making
a single network call.  Useful for:

- Reviewing the workspace structure before committing
- Running in CI without a real Notion token
- Demoing the tool to someone else

### 7. Fully tested with no external dependencies

The test suite (`tests/test_builder.py`) achieves full coverage of the
builder logic using `unittest.mock` — no real Notion account or token
required.  `notion_client` is stubbed at import time, so `pytest tests/` runs
completely offline.

---

## The Workspace It Builds

### 🏢 Companies — the account CRM

Your master list of target employers, modelled after an account list in a B2B
CRM.  Each row tracks a company's product, your fit rationale, open roles, and
next actions.

**Key properties:** Company Name · Product/Platform · Tier (1/2/3) · Status
pipeline · Remote Posture · Funding Stage · Why You Fit · Website / Careers /
LinkedIn · Next Action · Due Date

**Relations to:** Job Postings, Contacts

---

### 📋 Job Postings — role intelligence log

Every specific job posting you find goes here.  Captures technical
requirements, EHR/platform mentions, qualification gaps, and apply decision.

**Key properties:** Job Title · Role Type · Date Found · Salary Range · Job
Post URL · Required Technical Skills · EHR/Platform Mentioned · Do You Qualify?
· Gaps Identified · Apply?

**Relations to:** Companies

---

### 👥 Contacts — buying committee map

Your network mapped to specific companies.  Tracks connection degree, warm
intro availability, and outreach sequencing.

**Key properties:** Full Name · Title · Contact Type (Hiring Manager / Peer /
Recruiter / Executive / Alumni) · Priority · LinkedIn URL · Connection Degree ·
Warm Intro Available? · Next Action

**Relations to:** Companies, Outreach Log

---

### 📬 Outreach Log — activity tracker

Every message, DM, email, and follow-up logged here.  Prevents the embarrassing
double-message and ensures nothing falls through the cracks.

**Key properties:** Subject/Purpose · Date Sent · Channel · Message Type ·
Personalization Hook · Response Received? · Outcome

**Relations to:** Contacts, Companies

---

### 🧠 Gap Analysis — interview prep page

A structured, pre-filled page with two sections:

- **Strengths to Lead With** — domain knowledge, ITIL cert, cybersecurity
  stack, Finance degree, with a ready-to-use talking point for each
- **Gaps & Objections to Prepare For** — no direct SaaS experience, no quota
  history, relocation timing, salary target — each with a prepared rebuttal
  and mitigation strategy

---

### Seed Data (optional, via `--seed-data`)

Five pre-filled Companies rows:

| Company | Platform | Tier | Pre-written "Why You Fit" |
|---------|----------|------|---------------------------|
| Epic Systems | Epic EHR (Hyperspace, MyChart) | Tier 1 | ✅ Hospital IT credibility |
| Health Catalyst | DOS + Analytics Accelerators | Tier 1 | ✅ Finance degree for ROI conversations |
| Greenway Health | Intergy EHR + RCM | Tier 2 | ✅ Cert stack for HIPAA-heavy customers |
| Veeva Systems | Vault QMS/RIM + CRM | Tier 1 | ✅ Life sciences adjacency |
| ServiceNow | Now Platform (ITSM, Healthcare) | Tier 2 | ✅ ITIL cert = direct differentiator |

---

## Project Structure

```
notion-job-search/
│
├── notion_job_search/          # The Python package
│   ├── __init__.py             # Package metadata
│   ├── __main__.py             # Enables: python -m notion_job_search
│   ├── cli.py                  # argparse CLI, .env loading, exit codes
│   ├── client.py               # Notion SDK wrapper, auth, error handling
│   ├── builder.py              # Workspace orchestration logic
│   └── config.py               # All schemas, seed data, gap analysis content
│
├── tests/
│   ├── __init__.py
│   └── test_builder.py         # 40+ unit tests, runs 100% offline
│
├── .env.example                # Template — copy to .env and fill in
├── .gitignore                  # Includes .env
├── requirements.txt
├── setup.py                    # pip-installable, registers CLI entry point
└── README.md
```

---

## Prerequisites

- Python 3.10 or higher
- A free [Notion](https://notion.so) account
- A Notion Internal Integration (takes ~2 minutes to create)
- An existing Notion page to use as the workspace root

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/notion-job-search.git
cd notion-job-search
```

### 2. Create a virtual environment and install dependencies

```bash
python -m venv venv
source venv/bin/activate      # macOS/Linux
# venv\Scripts\activate       # Windows

pip install -r requirements.txt
```

### 3. Create a Notion integration

1. Go to [https://www.notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Click **+ New integration**
3. Give it a name (e.g. "Job Search Builder") and select your workspace
4. Copy the **Internal Integration Token** — it starts with `secret_`

### 4. Connect the integration to your root page

1. Open the Notion page you want to use as the parent (or create a blank one)
2. Click the `···` menu (top-right) → **Connections** → find your integration → **Connect**
3. Copy the page's ID from its URL:
   `https://notion.so/myworkspace/`**`1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d`**`?v=...`

### 5. Configure your `.env` file

```bash
cp .env.example .env
```

Edit `.env`:

```dotenv
NOTION_TOKEN=secret_your_token_here
NOTION_PARENT_PAGE_ID=1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d
```

---

## Running the Script

### Preview first (recommended)

```bash
python -m notion_job_search --dry-run
```

This prints every payload that *would* be sent to the API — all database
schemas, all seven relation patches, the Gap Analysis block structure — without
making a single network call.

### Build the workspace

```bash
python -m notion_job_search
```

### Build the workspace + seed data

```bash
python -m notion_job_search --seed-data
```

### Build with verbose logging

```bash
python -m notion_job_search --seed-data --verbose
```

### If you installed the package (`pip install -e .`)

```bash
notion-job-search --seed-data
```

---

## CLI Reference

```
usage: notion-job-search [-h] [--dry-run] [--seed-data]
                          [--token TOKEN] [--parent PAGE_ID]
                          [--verbose]

Scaffold a job-search CRM workspace in Notion — four linked
databases modelled on a B2B sales pipeline.

options:
  -h, --help         show this help message and exit
  --dry-run          Simulate all operations and print the payloads that
                     WOULD be sent to the Notion API, without making any
                     actual API calls.
  --seed-data        After scaffolding the databases, insert five sample
                     healthcare IT company rows with realistic 'Why You
                     Fit' notes.
  --token TOKEN      Notion integration token.  Overrides the NOTION_TOKEN
                     environment variable.
  --parent PAGE_ID   Notion parent page ID.  Overrides
                     NOTION_PARENT_PAGE_ID environment variable.
  --verbose          Enable DEBUG-level logging.
```

**Example output (successful run with `--seed-data`):**

```
============================================================
  Building Job Search HQ workspace
============================================================

[Step 1/5] Creating parent page …
✅ Created parent page 'Job Search HQ'  (id: abc-123...)

[Step 2/5] Creating databases …
✅ Created database '🏢 Companies          '  (id: ...)
✅ Created database '📋 Job Postings       '  (id: ...)
✅ Created database '👥 Contacts           '  (id: ...)
✅ Created database '📬 Outreach Log       '  (id: ...)

[Step 3/5] Wiring up cross-database relations …
🔗 Linked  🏢 Companies          [Job Postings]         → 📋 Job Postings
🔗 Linked  🏢 Companies          [Contacts]             → 👥 Contacts
🔗 Linked  📋 Job Postings       [Company]              → 🏢 Companies
🔗 Linked  👥 Contacts           [Company]              → 🏢 Companies
🔗 Linked  👥 Contacts           [Outreach Log]         → 📬 Outreach Log
🔗 Linked  📬 Outreach Log       [Contact]              → 👥 Contacts
🔗 Linked  📬 Outreach Log       [Company]              → 🏢 Companies

[Step 4/5] Seeding sample data …
  ➕ Seeded company: Epic Systems
  ➕ Seeded company: Health Catalyst
  ➕ Seeded company: Greenway Health
  ➕ Seeded company: Veeva Systems
  ➕ Seeded company: ServiceNow

[Step 5/5] Creating Gap Analysis page …
✅ Created 'Gap Analysis' page  (id: ...)

============================================================
  ✅ Workspace build complete!
============================================================
```

---

## Running the Tests

The test suite runs completely offline — `notion_client` is mocked at import
time, so no token or internet connection is needed.

```bash
pytest tests/ -v
```

Expected output:

```
tests/test_builder.py::TestRichText::test_returns_list PASSED
tests/test_builder.py::TestRichText::test_correct_structure PASSED
...
tests/test_builder.py::TestBuildWorkspace::test_dry_run_returns_dict_with_all_keys PASSED
...
40 passed in 0.12s
```

---

## Design Decisions

### Why `notion-client` (SDK) instead of `requests`?

The official SDK handles auth headers, retries on 429 (rate-limit), and exposes
typed `APIResponseError` exceptions.  Using `requests` directly would require
reimplementing all of this and produces noisier, less maintainable code.

### Why separate config from builder?

A hiring manager reviewing this code can read `config.py` and immediately
understand the full data model without reading a single line of API logic.  The
schemas are just Python dicts — no special knowledge required.  This is the
same separation used in Django's `models.py` vs `views.py` pattern.

### Why `--dry-run`?

CI pipelines and code reviewers should be able to validate the logic without
needing a live Notion account.  `--dry-run` makes the tool testable in any
environment and demonstrates awareness of operational concerns beyond just
"make it work."

### Why pin to `Notion-Version: 2022-06-28`?

Notion released a new API version in September 2025 with breaking changes.
Pinning the version in one place (`config.NOTION_API_VERSION`) means upgrading
is a single-line change, and the current version is explicit and auditable.

### Why create databases before patching relations?

This is a hard constraint of the Notion API: you cannot create a relation
property pointing at a database that doesn't exist yet.  The two-pass approach
(create all DBs → patch all relations) is the only correct solution.

---

## Extending the Project

**Add a new database property:**
Edit the relevant `SCHEMA_*` dict in `config.py`.  No other file needs to change.

**Add more seed companies:**
Add an entry to `SEED_COMPANIES` in `config.py`.

**Add a new database:**
1. Add its name to `DB_NAMES` in `config.py`
2. Define its schema as `SCHEMA_NEWDB` in `config.py`
3. Add it to the `db_schemas` dict in `builder.build_workspace()`
4. Add its relation entries to the `relations` list in `builder.patch_relations()`

**Export workspace IDs for use in other scripts:**
`build_workspace()` returns a dict of all created IDs — pipe them into any
downstream automation.

---

## License

MIT License — see [LICENSE](LICENSE) for details.
