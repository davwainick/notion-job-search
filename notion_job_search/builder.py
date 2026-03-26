"""
builder.py — Orchestrates the creation of the entire job search workspace.

Responsibility breakdown
------------------------
* ``create_parent_page``    — creates the top-level workspace page
* ``create_database``       — generic wrapper for POST /v1/databases
* ``patch_relations``       — wires up cross-database relation properties
* ``seed_companies``        — inserts generic placeholder company rows
* ``create_gap_analysis``   — builds an empty Gap Analysis template page
* ``update_gap_analysis``   — populates Gap Analysis with user-supplied content
* ``build_workspace``       — top-level orchestrator called by CLI and GUI

All functions accept a ``dry_run`` flag.  When *True* they print what they
*would* do instead of hitting the API, which is useful for previewing the
workspace structure without consuming Notion API quota.

IMPORTANT NOTE ON SDK USAGE
----------------------------
The ``notion-client`` SDK's ``databases.create()`` and ``databases.update()``
methods use an internal ``pick()`` function that whitelists only certain kwargs
before forwarding them to the API body.  Crucially, ``properties`` is NOT in
the whitelist for either method, so passing ``properties=...`` as a kwarg
silently drops it — causing Notion to return
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
    SCHEMA_COMPANIES,
    SCHEMA_CONTACTS,
    SCHEMA_JOB_POSTINGS,
    SCHEMA_OUTREACH_LOG,
    SEED_COMPANIES,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal block factory helpers
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
    workspace_name: str = "Job Search HQ",
    *,
    dry_run: bool = False,
) -> str:
    """
    Create the top-level workspace page under the user's root Notion page.

    Args:
        client:                 Authenticated Notion client.
        notion_parent_page_id:  ID of the existing Notion page that will
                                contain the workspace.
        workspace_name:         Display name for the workspace page.
        dry_run:                If *True*, print the payload and return a
                                placeholder ID without hitting the API.

    Returns:
        The Notion page ID of the newly created (or simulated) parent page.
    """
    payload = {
        "parent": {"type": "page_id", "page_id": notion_parent_page_id},
        "icon": {"type": "emoji", "emoji": "🗂️"},
        "properties": {
            "title": {"title": _rich_text(workspace_name)}
        },
        "children": [
            _callout(
                f"Welcome to {workspace_name} — your personal job-search CRM. "
                "Use Companies as your account list, Job Postings as your "
                "opportunity log, Contacts as your network map, "
                "and Outreach Log as your activity tracker.",
                "🗂️",
            ),
            _divider(),
            _heading_2("📌 Quick Links"),
            _paragraph(
                "Your four linked databases live below. "
                "Open the Gap Analysis page to fill in your strengths and "
                "interview prep notes."
            ),
        ],
    }

    if dry_run:
        logger.info("[DRY RUN] Would create parent page '%s':", workspace_name)
        logger.info(json.dumps(payload, indent=2))
        return "dry-run-parent-page-id"

    response = safe_api_call(
        client.pages.create,
        **payload,
        context=f"creating parent page '{workspace_name}'",
    )
    page_id: str = response["id"]
    logger.info("✅ Created parent page '%s'  (id: %s)", workspace_name, page_id)
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
    the SDK's ``databases.update()`` method also excludes ``properties``
    from its ``pick()`` whitelist.

    The relation map:
    - Companies      → Job Postings, Contacts
    - Job Postings   → Companies
    - Contacts       → Companies, Outreach Log
    - Outreach Log   → Contacts, Companies

    Args:
        client:  Authenticated Notion client.
        db_ids:  Dict mapping ``db_key`` → Notion database ID.
        dry_run: If *True*, print what would be patched without hitting the API.
    """
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
    Insert generic placeholder company rows into the Companies database.

    These rows demonstrate the database schema without containing any
    industry-specific or personal content.  Users should replace or
    supplement them with their actual target companies.

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
    Create a structured but empty Gap Analysis template page in Notion.

    The page is created with two section headings and instructional
    placeholder callout blocks.  The user fills in their own content
    either through the GUI (which calls ``update_gap_analysis``) or
    directly in Notion.

    Args:
        client:         Authenticated Notion client.
        parent_page_id: ID of the workspace parent page.
        dry_run:        If *True*, print what would be created without API calls.

    Returns:
        The Notion page ID of the newly created (or simulated) Gap Analysis page.
    """
    blocks: list[dict] = [
        _callout(
            "Use this page to prepare for interviews. "
            "Fill in your strengths and talking points in the first section, "
            "then list any objections a hiring manager might raise along with "
            "your prepared rebuttal for each.",
            "🧠",
        ),
        _divider(),
        _heading_2("💪 Strengths to Lead With"),
        _callout(
            "Add your strengths here — e.g. relevant domain knowledge, "
            "certifications, transferable skills, and a talking point for each. "
            "Use the GUI or edit this page directly in Notion.",
            "✏️",
        ),
        _divider(),
        _heading_2("⚠️ Gaps & Objections to Prepare For"),
        _callout(
            "Add objections a hiring manager might raise here — "
            "e.g. gaps in experience, career pivot concerns, location, salary. "
            "For each one write a short rebuttal and a mitigation strategy.",
            "✏️",
        ),
    ]

    if dry_run:
        logger.info(
            "[DRY RUN] Would create 'Gap Analysis' template page with %d blocks.",
            len(blocks),
        )
        return "dry-run-gap-analysis-id"

    response = safe_api_call(
        client.pages.create,
        parent={"type": "page_id", "page_id": parent_page_id},
        icon={"type": "emoji", "emoji": "🧠"},
        properties={"title": {"title": _rich_text("Gap Analysis")}},
        children=blocks,
        context="creating 'Gap Analysis' template page",
    )
    page_id: str = response["id"]
    logger.info("✅ Created 'Gap Analysis' page  (id: %s)", page_id)
    return page_id


def update_gap_analysis(
    client: Client,
    gap_page_id: str,
    strengths: list[dict],
    gaps: list[dict],
) -> None:
    """
    Populate the Gap Analysis page with user-supplied content.

    Replaces all existing blocks on the page with freshly built content
    from the provided strengths and gaps lists.  Called from the GUI after
    the user fills in the Gap Analysis input screen.

    If both lists are empty this function returns immediately without
    making any API calls.

    Args:
        client:       Authenticated Notion client.
        gap_page_id:  Notion page ID of the Gap Analysis page.
        strengths:    List of dicts with keys ``"strength"`` and
                      ``"talking_point"``.
        gaps:         List of dicts with keys ``"objection"``, ``"rebuttal"``,
                      and ``"mitigation"``.
    """
    if not strengths and not gaps:
        logger.info("update_gap_analysis: nothing to update, both lists empty.")
        return

    # --- Delete existing blocks ---
    existing = safe_api_call(
        client.blocks.children.list,
        gap_page_id,
        context="listing existing Gap Analysis blocks",
    )
    for block in existing.get("results", []):
        safe_api_call(
            client.blocks.delete,
            block["id"],
            context=f"deleting block {block['id']}",
        )

    # --- Build new content ---
    new_blocks: list[dict] = [
        _callout(
            "Use this page to prepare for interviews. "
            "Lead with your Strengths. Anticipate every Objection.",
            "🧠",
        ),
        _divider(),
        _heading_2("💪 Strengths to Lead With"),
    ]

    for item in strengths:
        strength = item.get("strength", "").strip()
        talking_point = item.get("talking_point", "").strip()
        if not strength:
            continue
        new_blocks.append(_heading_3(f"✅ {strength}"))
        if talking_point:
            new_blocks.append(_bulleted_item(f"Talking point: {talking_point}"))

    new_blocks.extend([
        _divider(),
        _heading_2("⚠️ Gaps & Objections to Prepare For"),
    ])

    for item in gaps:
        objection = item.get("objection", "").strip()
        rebuttal = item.get("rebuttal", "").strip()
        mitigation = item.get("mitigation", "").strip()
        if not objection:
            continue
        new_blocks.append(_heading_3(f"🔴 {objection}"))
        if rebuttal:
            new_blocks.append(_callout(f"Rebuttal: {rebuttal}", "💬"))
        if mitigation:
            new_blocks.append(_bulleted_item(f"Mitigation: {mitigation}"))

    # Notion limits blocks.children.append to 100 blocks per call
    chunk_size = 100
    for i in range(0, len(new_blocks), chunk_size):
        chunk = new_blocks[i: i + chunk_size]
        safe_api_call(
            client.blocks.children.append,
            gap_page_id,
            children=chunk,
            context="appending Gap Analysis content",
        )

    logger.info(
        "✅ Updated Gap Analysis with %d strength(s) and %d gap(s).",
        len(strengths),
        len(gaps),
    )


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------

def build_workspace(
    client: Client,
    notion_parent_page_id: str,
    workspace_name: str = "Job Search HQ",
    *,
    dry_run: bool = False,
    seed_data: bool = False,
    progress_callback: Any = None,
) -> dict[str, str]:
    """
    Orchestrate the full workspace build in the correct dependency order.

    Order of operations
    -------------------
    1. Create the workspace parent page.
    2. Create all four databases (no relations yet — target IDs not known).
    3. Patch relations onto each database now that all IDs are available.
    4. (Optional) Seed generic placeholder company rows.
    5. Create the Gap Analysis template page.

    Args:
        client:                 Authenticated Notion client.
        notion_parent_page_id:  ID of the user's root Notion page.
        workspace_name:         Display name for the workspace (default:
                                ``"Job Search HQ"``).
        dry_run:                If *True*, simulate all operations and print
                                payloads without hitting the API.
        seed_data:              If *True*, insert 3 generic placeholder rows.
        progress_callback:      Optional callable that accepts a string message.
                                Called at the start of each step so a GUI can
                                update a progress label.

    Returns:
        A dict with keys ``"parent_page_id"``, ``"gap_analysis_id"``,
        ``"notion_url"``, and one key per database
        (``"companies"``, ``"job_postings"``, ``"contacts"``,
        ``"outreach_log"``), each mapping to its Notion ID.
    """
    def _progress(msg: str) -> None:
        logger.info(msg)
        if progress_callback:
            progress_callback(msg)

    _progress("=" * 60)
    _progress(f"  Building workspace: {workspace_name}")
    if dry_run:
        _progress("  *** DRY RUN — no API calls will be made ***")
    _progress("=" * 60)

    # Step 1: Parent page
    _progress(f"\n[Step 1/5] Creating parent page '{workspace_name}' …")
    parent_page_id = create_parent_page(
        client, notion_parent_page_id, workspace_name, dry_run=dry_run
    )

    # Step 2: Databases
    _progress("\n[Step 2/5] Creating databases …")
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
    _progress("\n[Step 3/5] Wiring up cross-database relations …")
    patch_relations(client, db_ids, dry_run=dry_run)

    # Step 4: Seed data (optional)
    if seed_data:
        _progress("\n[Step 4/5] Seeding sample data …")
        seed_companies(client, db_ids, dry_run=dry_run)
    else:
        _progress("\n[Step 4/5] Skipping seed data (pass seed_data=True to enable).")

    # Step 5: Gap Analysis page
    _progress("\n[Step 5/5] Creating Gap Analysis page …")
    gap_analysis_id = create_gap_analysis(
        client, parent_page_id, dry_run=dry_run
    )

    # Build a direct Notion URL (hyphens stripped from the page ID)
    clean_id = parent_page_id.replace("-", "")
    notion_url = f"https://notion.so/{clean_id}"

    _progress("\n" + "=" * 60)
    _progress("  ✅ Workspace build complete!")
    _progress("=" * 60)

    return {
        "parent_page_id":  parent_page_id,
        "gap_analysis_id": gap_analysis_id,
        "notion_url":      notion_url,
        **db_ids,
    }