"""
config.py — All database schemas and seed data are defined here.

Keeping the schema definitions entirely separate from the API call logic
demonstrates separation of concerns and makes it trivial to add, rename,
or remove Notion properties without touching any network code.

Each ``SCHEMA_*`` dict maps directly to the ``properties`` object accepted by
the Notion Databases API (POST /v1/databases).  Relation properties are
intentionally omitted here and patched in afterwards by ``builder.py`` once
all four database IDs are known.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Notion API version pin — avoids opt-in breaking changes from 2025-09-03
# ---------------------------------------------------------------------------
NOTION_API_VERSION = "2022-06-28"

# ---------------------------------------------------------------------------
# Database display names (used as the inline title inside each DB page)
# ---------------------------------------------------------------------------
DB_NAMES = {
    "companies": "🏢 Companies",
    "job_postings": "📋 Job Postings",
    "contacts": "👥 Contacts",
    "outreach_log": "📬 Outreach Log",
}

# ---------------------------------------------------------------------------
# Helper lambdas for concise schema declarations
# ---------------------------------------------------------------------------
def _select(*options: str) -> dict:
    """Return a Notion ``select`` property config with the given option names."""
    return {"select": {"options": [{"name": o} for o in options]}}


def _text() -> dict:
    """Return a Notion ``rich_text`` property config."""
    return {"rich_text": {}}


def _url() -> dict:
    """Return a Notion ``url`` property config."""
    return {"url": {}}


def _date() -> dict:
    """Return a Notion ``date`` property config."""
    return {"date": {}}


def _checkbox() -> dict:
    """Return a Notion ``checkbox`` property config."""
    return {"checkbox": {}}


# ---------------------------------------------------------------------------
# 1. Companies schema
# ---------------------------------------------------------------------------
SCHEMA_COMPANIES: dict = {
    "Company Name": {"title": {}},
    "Product/Platform": _text(),
    "Tier": _select("Tier 1", "Tier 2", "Tier 3"),
    "Status": _select(
        "Researching",
        "Targeting",
        "Contacted",
        "Applied",
        "Phone Screen",
        "Interview",
        "Offer",
        "Closed",
        "Watching",
    ),
    "HQ Location": _text(),
    "Remote Posture": _select(
        "Fully Remote",
        "Hybrid",
        "On-Site",
        "Flexible",
    ),
    "Company Size": _select(
        "1-50",
        "51-200",
        "201-500",
        "501-1000",
        "1001-5000",
        "5001-10000",
        "10000+",
    ),
    "Funding Stage": _select(
        "Bootstrapped",
        "Seed",
        "Series A",
        "Series B",
        "Series C+",
        "Public",
        "Private Equity",
    ),
    "Open Role?": _checkbox(),
    "Why You Fit": _text(),
    "Website": _url(),
    "Careers Page": _url(),
    "LinkedIn Page": _url(),
    "Last Checked": _date(),
    "Next Action": _text(),
    "Due Date": _date(),
    "Notes": _text(),
    # Relations to Job Postings and Contacts are patched in after DB creation.
}

# ---------------------------------------------------------------------------
# 2. Job Postings schema
# ---------------------------------------------------------------------------
SCHEMA_JOB_POSTINGS: dict = {
    "Job Title": {"title": {}},
    "Role Type": _select(
        "Full-Time",
        "Contract",
        "Part-Time",
        "Internship",
        "Other",
    ),
    "Date Found": _date(),
    "Location": _text(),
    "Salary Range": _text(),
    "Job Post URL": _url(),
    "Required Technical Skills": _text(),
    "Platform/Tool Mentioned": _text(),
    "Preferred Skills": _text(),
    "Soft Skills Emphasized": _text(),
    "Interesting Keywords": _text(),
    "Do You Qualify?": _select("Yes", "Partially", "No"),
    "Gaps Identified": _text(),
    "Apply?": _select("Yes", "No", "Later", "Applied", "Closed"),
    "Notes": _text(),
    # Relation to Companies patched in after DB creation.
}

# ---------------------------------------------------------------------------
# 3. Contacts schema
# ---------------------------------------------------------------------------
SCHEMA_CONTACTS: dict = {
    "Full Name": {"title": {}},
    "Title": _text(),
    "Contact Type": _select(
        "Hiring Manager",
        "Peer in Role",
        "Recruiter",
        "Executive",
        "Alumni",
        "Referral Source",
    ),
    "Priority": _select("HIGH", "MED", "LOW"),
    "LinkedIn URL": _url(),
    "Email": _text(),
    "Connection Degree": _select("1st", "2nd", "3rd", "No connection"),
    "Warm Intro Available?": _checkbox(),
    "How You Know Them": _text(),
    "Date Connected": _date(),
    "Last Touchpoint": _date(),
    "Notes/Intel": _text(),
    "Next Action": _text(),
    "Due Date": _date(),
    # Relations to Companies and Outreach Log patched in after DB creation.
}

# ---------------------------------------------------------------------------
# 4. Outreach Log schema
# ---------------------------------------------------------------------------
SCHEMA_OUTREACH_LOG: dict = {
    "Subject/Purpose": {"title": {}},
    "Date Sent": _date(),
    "Channel": _select(
        "LinkedIn DM",
        "Email",
        "LinkedIn InMail",
        "Phone",
        "Referral",
        "Other",
    ),
    "Message Type": _select(
        "Connection Request",
        "Introduction",
        "Role Inquiry",
        "Informational Ask",
        "Application Follow-Up",
        "Thank You",
        "Check-In",
    ),
    "Personalization Hook": _text(),
    "Response Received?": _checkbox(),
    "Response Date": _date(),
    "Response Summary": _text(),
    "Follow-Up Due": _date(),
    "Follow-Up Sent?": _checkbox(),
    "Outcome": _select(
        "Pending",
        "Positive Response",
        "Call Scheduled",
        "Referred",
        "No Response",
        "Closed",
    ),
    "Notes": _text(),
    # Relations to Contacts and Companies patched in after DB creation.
}

# ---------------------------------------------------------------------------
# Generic seed data — 3 placeholder companies for demonstration
# ---------------------------------------------------------------------------
SEED_COMPANIES: list[dict] = [
    {
        "name": "Acme Corp",
        "platform": "Enterprise SaaS Platform",
        "tier": "Tier 1",
        "status": "Researching",
        "hq": "San Francisco, CA",
        "remote": "Hybrid",
        "size": "1001-5000",
        "funding": "Public",
        "open_role": True,
        "why_fit": "Add your fit rationale here — what skills and experience make you a strong candidate for this company?",
        "website": "https://www.example.com",
        "careers": "https://www.example.com/careers",
        "linkedin": "https://www.linkedin.com/company/example",
        "next_action": "Research the company and identify a contact to reach out to",
    },
    {
        "name": "Example Inc",
        "platform": "Cloud Infrastructure Tools",
        "tier": "Tier 2",
        "status": "Targeting",
        "hq": "Austin, TX",
        "remote": "Fully Remote",
        "size": "201-500",
        "funding": "Series B",
        "open_role": True,
        "why_fit": "Add your fit rationale here — what skills and experience make you a strong candidate for this company?",
        "website": "https://www.example.com",
        "careers": "https://www.example.com/careers",
        "linkedin": "https://www.linkedin.com/company/example",
        "next_action": "Find a warm intro or reach out directly via LinkedIn",
    },
    {
        "name": "Sample Co",
        "platform": "Data Analytics Software",
        "tier": "Tier 2",
        "status": "Watching",
        "hq": "New York, NY",
        "remote": "On-Site",
        "size": "51-200",
        "funding": "Series A",
        "open_role": False,
        "why_fit": "Add your fit rationale here — what skills and experience make you a strong candidate for this company?",
        "website": "https://www.example.com",
        "careers": "https://www.example.com/careers",
        "linkedin": "https://www.linkedin.com/company/example",
        "next_action": "Set a job alert and check back monthly",
    },
]