"""
builder.py — Orchestrates the creation of the entire Job Search HQ workspace.

Responsibility breakdown
------------------------
* ``create_parent_page``   — creates the top-level "Job Search HQ" page
* ``create_database``      — generic wrapper for POST /v1/databases
* ``patch_relations``      — wires up cross-database relation properties
* ``create_gap_analysis``  — builds the formatted Gap Analysis sub-page
* ``seed_companies``       — inserts 5 sample company rows
* ``build_workspace``      — top-level orchestrator called by the CLI

All functions accept a ``dry_run`` flag.  When *True* they print what they
*would* do instead of hitting the API, which is useful for previewing the
workspace structure without consuming Notion API quota.

IMPORTANT NOTE ON SDK USAGE
----------------------------
The ``notion-client`` SDK's ``databases.create()`` and ``databases.update()``
methods use an internal ``pick()`` function that whitelists only certain kwargs
before forwarding them to the API body.  Crucially, ``properties`` is NOT in
the whitelist for either method (as of the current SDK version), so passing
``properties=...`` as a kwarg silently drops it — causing Notion to return
``body.properties should be defined, instead was undefined``.

The fix is to call ``client.request()`` directly for those two operations,
which bypasses ``pick()`` and sends the full body as-is.  ``client.request()``
is the documented escape hatch for this exact scenario and still benefits from
the SDK's auth headers and retry logic.

``pages.create()`` does include ``properties`` and ``children`` in its
whitelist, so it is called normally via the SDK method.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from notion_client import Client  # type: ignore

from .client import safe_api_call
from .config import (
    DB_NAMES,
    GAP_ANALYSIS_GAPS,
    GAP_ANALYSIS_STRENGTHS,
    SCHEMA_COMPANIES,
    SCHEMA_CONTACTS,
    SCHEMA_JOB_POSTINGS,
    SCHEMA_OUTREACH_LOG,
    SEED_COMPANIES,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _rich_text(content: str) -> list[dict]:
    """
    Wrap a plain string in a Notion ``rich_text`` block list.

    Args:
        content: Plain-text string to wrap.

    Returns:
        A list containing a single rich-text object suitable for use in
        Notion page / block payloads.
    """
    return [{"type": "text", "text": {"content": content}}]


def _heading_2(text: str) -> dict:
    """Return a Notion ``heading_2`` block dict."""
    return {
        "object": "block",
        "type": "heading_2",
        "heading_2": {"rich_text": _rich_text(text)},
    }


def _heading_3(text: str) -> dict:
    """Return a Notion ``heading_3`` block dict."""
    return {
        "object": "block",
        "type": "heading_3",
        "heading_3": {"rich_text": _rich_text(text)},
    }


def _paragraph(text: str) -> dict:
    """Return a Notion ``paragraph`` block dict."""
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": _rich_text(text)},
    }


def _divider() -> dict:
    """Return a Notion divider block dict."""
    return {"object": "block", "type": "divider", "divider": {}}


def _bulleted_item(text: str) -> dict:
    """Return a Notion ``bulleted_list_item`` block dict."""
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": _rich_text(text)},
    }


def _callout(text: str, emoji: str = "💡") -> dict:
    """Return a Notion callout block dict."""
    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": _rich_text(text),
            "icon": {"type": "emoji", "emoji": emoji},
        },
    }


# ---------------------------------------------------------------------------
# Parent page
# ---------------------------------------------------------------------------

def create_parent_page(
    client: Client,
    notion_parent_page_id: str,
    *,
    dry_run: bool = False,
) -> str:
    """
    Create the top-level "Job Search HQ" page under the user's root page.

    Uses ``client.pages.create()`` which correctly includes ``properties``
    and ``children`` in its SDK whitelist.

    Args:
        client:                 Authenticated Notion client.
        notion_parent_page_id:  ID of the existing Notion page that will
                                contain Job Search HQ.
        dry_run:                If *True*, print the payload and return a
                                placeholder ID without hitting the API.

    Returns:
        The Notion page ID of the newly created (or simulated) parent page.
    """
    payload = {
        "parent": {"type": "page_id", "page_id": notion_parent_page_id},
        "icon": {"type": "emoji", "emoji": "🗂️"},
        "properties": {
            "title": {"title": _rich_text("Job Search HQ")}
        },
        "children": [
            _callout(
                "This workspace is a B2B-style job-search CRM. "
                "Use Companies as your account list, Job Postings as your "
                "opportunity log, Contacts as your buying-committee map, "
                "and Outreach Log as your activity tracker.",
                "🗂️",
            ),
            _divider(),
            _heading_2("📌 Quick Links"),
            _paragraph("Use the linked databases below — linked views live in each section."),
        ],
    }

    if dry_run:
        logger.info("[DRY RUN] Would create parent page 'Job Search HQ':")
        logger.info(json.dumps(payload, indent=2))
        return "dry-run-parent-page-id"

    response = safe_api_call(
        client.pages.create,
        **payload,
        context="creating parent page 'Job Search HQ'",
    )
    page_id: str = response["id"]
    logger.info("✅ Created parent page 'Job Search HQ'  (id: %s)", page_id)
    return page_id


# ---------------------------------------------------------------------------
# Database creation
# ---------------------------------------------------------------------------

def create_database(
    client: Client,
    parent_page_id: str,
    db_key: str,
    schema: dict[str, Any],
    *,
    dry_run: bool = False,
) -> str:
    """
    Create a single Notion database as a child of *parent_page_id*.

    Uses ``client.request()`` directly (POST /v1/databases) rather than
    ``client.databases.create()`` because the SDK's ``databases.create``
    method uses an internal ``pick()`` whitelist that excludes ``properties``,
    causing it to be silently dropped from the request body.

    Args:
        client:         Authenticated Notion client.
        parent_page_id: ID of the page that will contain this database.
        db_key:         Key into :data:`config.DB_NAMES` (e.g. ``"companies"``).
        schema:         Property definitions dict (from ``config.py``).
        dry_run:        If *True*, print the payload and return a placeholder ID.

    Returns:
        The Notion database ID of the newly created (or simulated) database.
    """
    db_name = DB_NAMES[db_key]
    body = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": _rich_text(db_name),
        "is_inline": True,
        "properties": schema,
    }

    if dry_run:
        logger.info("[DRY RUN] Would create database '%s':", db_name)
        logger.info(json.dumps(body, indent=2))
        return f"dry-run-{db_key}-id"

    response = safe_api_call(
        client.request,
        path="databases",
        method="POST",
        body=body,
        context=f"creating database '{db_name}'",
    )
    db_id: str = response["id"]
    logger.info("✅ Created database '%-20s'  (id: %s)", db_name, db_id)
    return db_id


# ---------------------------------------------------------------------------
# Relation patching
# ---------------------------------------------------------------------------

def patch_relations(
    client: Client,
    db_ids: dict[str, str],
    *,
    dry_run: bool = False,
) -> None:
    """
    Wire up all cross-database relations after all four databases exist.

    Notion requires the target database to already exist before a relation
    property referencing it can be created.  This function performs a PATCH
    on each database to add the appropriate relation properties.

    Uses ``client.request()`` directly (PATCH /v1/databases/{id}) because
    the SDK's ``databases.update()`` method also uses ``pick()`` and excludes
    ``properties`` from its whitelist.

    The relation map (what each DB links to):
    - Companies      → Job Postings, Contacts
    - Job Postings   → Companies
    - Contacts       → Companies, Outreach Log
    - Outreach Log   → Contacts, Companies

    Args:
        client:  Authenticated Notion client.
        db_ids:  Dict mapping ``db_key`` → Notion database ID.
        dry_run: If *True*, print what would be patched without hitting the API.
    """
    # Each entry: (db_key, relation_property_name, target_db_key)
    relations: list[tuple[str, str, str]] = [
        ("companies",    "Job Postings",  "job_postings"),
        ("companies",    "Contacts",      "contacts"),
        ("job_postings", "Company",       "companies"),
        ("contacts",     "Company",       "companies"),
        ("contacts",     "Outreach Log",  "outreach_log"),
        ("outreach_log", "Contact",       "contacts"),
        ("outreach_log", "Company",       "companies"),
    ]

    for db_key, prop_name, target_key in relations:
        db_id = db_ids[db_key]
        target_id = db_ids[target_key]
        body = {
            "properties": {
                prop_name: {
                    "relation": {
                        "database_id": target_id,
                        "type": "single_property",
                        "single_property": {},
                    }
                }
            }
        }

        if dry_run:
            logger.info(
                "[DRY RUN] Would patch '%s' on '%s' → target '%s'",
                prop_name, DB_NAMES[db_key], DB_NAMES[target_key],
            )
            continue

        safe_api_call(
            client.request,
            path=f"databases/{db_id}",
            method="PATCH",
            body=body,
            context=(
                f"patching relation '{prop_name}' on '{DB_NAMES[db_key]}' "
                f"→ '{DB_NAMES[target_key]}'"
            ),
        )
        logger.info(
            "🔗 Linked  %-20s %-22s → %s",
            DB_NAMES[db_key], f"[{prop_name}]", DB_NAMES[target_key],
        )


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

def seed_companies(
    client: Client,
    db_ids: dict[str, str],
    *,
    dry_run: bool = False,
) -> None:
    """
    Insert five sample healthcare IT companies into the Companies database.

    Each row is pre-filled with realistic "Why You Fit" notes tied to the
    user's hospital IT background, certs, and target role types.

    Uses ``client.pages.create()`` which correctly includes ``properties``
    in its SDK whitelist.

    Args:
        client:  Authenticated Notion client.
        db_ids:  Dict mapping ``db_key`` → Notion database ID.
        dry_run: If *True*, print what would be inserted without hitting the API.
    """
    companies_db_id = db_ids["companies"]

    for company in SEED_COMPANIES:
        properties: dict[str, Any] = {
            "Company Name": {"title": _rich_text(company["name"])},
            "Product/Platform": {"rich_text": _rich_text(company["platform"])},
            "Tier": {"select": {"name": company["tier"]}},
            "Status": {"select": {"name": company["status"]}},
            "HQ Location": {"rich_text": _rich_text(company["hq"])},
            "Remote Posture": {"select": {"name": company["remote"]}},
            "Company Size": {"select": {"name": company["size"]}},
            "Funding Stage": {"select": {"name": company["funding"]}},
            "Open Role?": {"checkbox": company["open_role"]},
            "Why You Fit": {"rich_text": _rich_text(company["why_fit"])},
            "Website": {"url": company["website"]},
            "Careers Page": {"url": company["careers"]},
            "LinkedIn Page": {"url": company["linkedin"]},
            "Next Action": {"rich_text": _rich_text(company["next_action"])},
        }

        if dry_run:
            logger.info("[DRY RUN] Would insert company: %s", company["name"])
            continue

        safe_api_call(
            client.pages.create,
            parent={"database_id": companies_db_id},
            properties=properties,
            context=f"seeding company '{company['name']}'",
        )
        logger.info("  ➕ Seeded company: %s", company["name"])


# ---------------------------------------------------------------------------
# Gap Analysis page
# ---------------------------------------------------------------------------

def create_gap_analysis(
    client: Client,
    parent_page_id: str,
    *,
    dry_run: bool = False,
) -> str:
    """
    Create a richly formatted "Gap Analysis" Notion page.

    The page has two sections:
    1. **Strengths to Lead With** — pre-filled with the user's key assets
       (hospital IT domain, ITIL cert, cybersecurity stack, Finance degree).
    2. **Gaps / Objections to Prepare For** — the honest objections a hiring
       manager might raise, each paired with a prepared rebuttal and
       mitigation strategy.

    Uses ``client.pages.create()`` which correctly includes ``children``
    in its SDK whitelist.

    Args:
        client:         Authenticated Notion client.
        parent_page_id: ID of the "Job Search HQ" parent page.
        dry_run:        If *True*, print what would be created without API calls.

    Returns:
        The Notion page ID of the newly created (or simulated) Gap Analysis page.
    """
    blocks: list[dict] = [
        _callout(
            "Use this page in interview prep.  Lead with the Strengths. "
            "Anticipate every Objection and have your rebuttal ready.",
            "🧠",
        ),
        _divider(),
        # --- Strengths section ---
        _heading_2("💪 Strengths to Lead With"),
        _paragraph(
            "These are your genuine differentiators as a career-pivoting "
            "healthcare IT professional targeting SaaS Customer Success and "
            "Sales Engineering roles."
        ),
    ]

    for item in GAP_ANALYSIS_STRENGTHS:
        blocks.extend([
            _heading_3(f"✅ {item['asset']}"),
            _bulleted_item(f"Why it matters: {item['detail']}"),
            _bulleted_item(f"How to say it: {item['talking_point']}"),
        ])

    blocks.extend([
        _divider(),
        # --- Gaps section ---
        _heading_2("⚠️ Gaps & Objections to Prepare For"),
        _paragraph(
            "These are the objections a hiring manager or recruiter may raise. "
            "Prepare a 30-second verbal rebuttal for each before any screen."
        ),
    ])

    for item in GAP_ANALYSIS_GAPS:
        blocks.extend([
            _heading_3(f"🔴 {item['objection']}"),
            _bulleted_item(f"Risk: {item['risk']}"),
            _callout(f"Rebuttal: {item['rebuttal']}", "💬"),
            _bulleted_item(f"Mitigation strategy: {item['mitigation']}"),
        ])

    if dry_run:
        logger.info("[DRY RUN] Would create 'Gap Analysis' page with %d blocks.", len(blocks))
        return "dry-run-gap-analysis-id"

    response = safe_api_call(
        client.pages.create,
        parent={"type": "page_id", "page_id": parent_page_id},
        icon={"type": "emoji", "emoji": "🧠"},
        properties={"title": {"title": _rich_text("Gap Analysis")}},
        children=blocks,
        context="creating 'Gap Analysis' page",
    )
    page_id: str = response["id"]
    logger.info("✅ Created 'Gap Analysis' page  (id: %s)", page_id)
    return page_id


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------

def build_workspace(
    client: Client,
    notion_parent_page_id: str,
    *,
    dry_run: bool = False,
    seed_data: bool = False,
) -> dict[str, str]:
    """
    Orchestrate the full workspace build in the correct dependency order.

    Order of operations
    -------------------
    1. Create the "Job Search HQ" parent page.
    2. Create all four databases (no relations yet — target IDs not known).
    3. Patch relations onto each database now that all IDs are available.
    4. (Optional) Seed sample company rows.
    5. Create the Gap Analysis sub-page.

    Args:
        client:                 Authenticated Notion client.
        notion_parent_page_id:  ID of the user's root Notion page.
        dry_run:                If *True*, simulate all operations and print
                                payloads without hitting the API.
        seed_data:              If *True*, insert the five sample company rows.

    Returns:
        A dict with keys ``"parent_page_id"``, ``"gap_analysis_id"``, and one
        key per database (``"companies"``, ``"job_postings"``, ``"contacts"``,
        ``"outreach_log"``), each mapping to its Notion ID.
    """
    logger.info("=" * 60)
    logger.info("  Building Job Search HQ workspace")
    if dry_run:
        logger.info("  *** DRY RUN — no API calls will be made ***")
    logger.info("=" * 60)

    # Step 1: Parent page
    logger.info("\n[Step 1/5] Creating parent page …")
    parent_page_id = create_parent_page(
        client, notion_parent_page_id, dry_run=dry_run
    )

    # Step 2: Databases
    logger.info("\n[Step 2/5] Creating databases …")
    db_ids: dict[str, str] = {}

    db_schemas = {
        "companies":    SCHEMA_COMPANIES,
        "job_postings": SCHEMA_JOB_POSTINGS,
        "contacts":     SCHEMA_CONTACTS,
        "outreach_log": SCHEMA_OUTREACH_LOG,
    }

    for db_key, schema in db_schemas.items():
        db_ids[db_key] = create_database(
            client, parent_page_id, db_key, schema, dry_run=dry_run
        )

    # Step 3: Relations
    logger.info("\n[Step 3/5] Wiring up cross-database relations …")
    patch_relations(client, db_ids, dry_run=dry_run)

    # Step 4: Seed data (optional)
    if seed_data:
        logger.info("\n[Step 4/5] Seeding sample data …")
        seed_companies(client, db_ids, dry_run=dry_run)
    else:
        logger.info("\n[Step 4/5] Skipping seed data (use --seed-data to enable).")

    # Step 5: Gap Analysis page
    logger.info("\n[Step 5/5] Creating Gap Analysis page …")
    gap_analysis_id = create_gap_analysis(
        client, parent_page_id, dry_run=dry_run
    )

    logger.info("\n" + "=" * 60)
    logger.info("  ✅ Workspace build complete!")
    logger.info("=" * 60)

    return {
        "parent_page_id":  parent_page_id,
        "gap_analysis_id": gap_analysis_id,
        **db_ids,
    }