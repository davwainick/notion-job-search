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
        "1–50",
        "51–200",
        "201–500",
        "501–1000",
        "1001–5000",
        "5001–10000",
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
        "TCSM",
        "Sales Engineer",
        "Solutions Consultant",
        "Other",
    ),
    "Date Found": _date(),
    "Location": _text(),
    "Salary Range": _text(),
    "Job Post URL": _url(),
    "Required Technical Skills": _text(),
    "EHR/Platform Mentioned": _text(),
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
# Seed data — 5 sample companies
# ---------------------------------------------------------------------------
SEED_COMPANIES: list[dict] = [
    {
        "name": "Epic Systems",
        "platform": "Epic EHR (Hyperspace, MyChart, Cogito)",
        "tier": "Tier 1",
        "status": "Targeting",
        "hq": "Verona, WI",
        "remote": "Hybrid",
        "size": "10000+",
        "funding": "Private Equity",
        "open_role": True,
        "why_fit": (
            "4 years supporting Epic workflows at Stony Brook Hospital gives direct "
            "credibility with their target buyers. ITIL cert maps to Epic's "
            "structured implementation methodology. Can speak the language of "
            "clinical staff, IT leadership, and C-suite simultaneously."
        ),
        "website": "https://www.epic.com",
        "careers": "https://www.epic.com/careers",
        "linkedin": "https://www.linkedin.com/company/epic-systems/",
        "next_action": "Identify Customer Success Manager openings in Nashville region",
    },
    {
        "name": "Health Catalyst",
        "platform": "DOS (Data Operating System) + Analytics Accelerators",
        "tier": "Tier 1",
        "status": "Researching",
        "hq": "Salt Lake City, UT",
        "remote": "Fully Remote",
        "size": "1001–5000",
        "funding": "Public",
        "open_role": True,
        "why_fit": (
            "Hospital IT background means I understand the data pain points their "
            "platform solves. Finance degree enables ROI conversations with CFOs. "
            "Cybersecurity certs address compliance questions that often stall deals "
            "in health system procurement."
        ),
        "website": "https://www.healthcatalyst.com",
        "careers": "https://www.healthcatalyst.com/careers",
        "linkedin": "https://www.linkedin.com/company/health-catalyst/",
        "next_action": "Read latest 10-K and two customer case studies before outreach",
    },
    {
        "name": "Greenway Health",
        "platform": "Intergy EHR + Revenue Cycle Management",
        "tier": "Tier 2",
        "status": "Watching",
        "hq": "Tampa, FL",
        "remote": "Hybrid",
        "size": "1001–5000",
        "funding": "Private Equity",
        "open_role": False,
        "why_fit": (
            "Greenway focuses on ambulatory/specialty practices — adjacent to the "
            "hospital space I know. CSAP and CSIS certs signal security fluency "
            "relevant to their HIPAA-heavy customer base. Smaller org = faster "
            "path to Senior CSM or SE role."
        ),
        "website": "https://www.greenwayhealth.com",
        "careers": "https://www.greenwayhealth.com/careers",
        "linkedin": "https://www.linkedin.com/company/greenway-health/",
        "next_action": "Set job alert; check back in 30 days",
    },
    {
        "name": "Veeva Systems",
        "platform": "Veeva Vault (QMS, RIM, MedComms) + CRM",
        "tier": "Tier 1",
        "status": "Researching",
        "hq": "Pleasanton, CA",
        "remote": "Fully Remote",
        "size": "5001–10000",
        "funding": "Public",
        "open_role": True,
        "why_fit": (
            "Life sciences SaaS is adjacent to healthcare IT — compliance, "
            "regulated workflows, and clinical data are common threads. Finance "
            "degree + ITIL is a strong combo for their Solutions Consulting track. "
            "Veeva's Customer Success is well-defined with clear comp structures."
        ),
        "website": "https://www.veeva.com",
        "careers": "https://careers.veeva.com",
        "linkedin": "https://www.linkedin.com/company/veeva-systems/",
        "next_action": "Reach out to Veeva SE on LinkedIn for informational chat",
    },
    {
        "name": "ServiceNow",
        "platform": "Now Platform (ITSM, HRSD, Healthcare & Life Sciences workflows)",
        "tier": "Tier 2",
        "status": "Targeting",
        "hq": "Santa Clara, CA",
        "remote": "Hybrid",
        "size": "10000+",
        "funding": "Public",
        "open_role": True,
        "why_fit": (
            "ITIL cert is the single best differentiator for a ServiceNow CSM role "
            "— the platform is built around ITIL frameworks. Hospital IT experience "
            "maps directly to their Healthcare vertical. Path from CSM → Solutions "
            "Consultant is well-documented internally."
        ),
        "website": "https://www.servicenow.com",
        "careers": "https://careers.servicenow.com",
        "linkedin": "https://www.linkedin.com/company/servicenow/",
        "next_action": "Find Nashville-based ServiceNow SE to connect with on LinkedIn",
    },
]

# ---------------------------------------------------------------------------
# Gap Analysis page content
# ---------------------------------------------------------------------------
GAP_ANALYSIS_STRENGTHS: list[dict] = [
    {
        "asset": "Hospital IT Domain Knowledge",
        "detail": (
            "4 years at Stony Brook Hospital means I speak the language of nurses, "
            "physicians, IT directors, and compliance officers. Most SaaS CSMs have "
            "to learn this on the job."
        ),
        "talking_point": (
            "\"I've sat on the customer side of this exact conversation — I know "
            "what keeps a CIO up at night and how clinical staff actually use these "
            "tools day-to-day.\""
        ),
    },
    {
        "asset": "ITIL v4 Certification",
        "detail": (
            "Industry-standard framework for IT service management. Directly relevant "
            "to ServiceNow, Epic, and any platform sold into regulated environments."
        ),
        "talking_point": (
            "\"My ITIL background means I can map your platform's capabilities to the "
            "customer's existing ITSM processes from day one — no ramp-up required.\""
        ),
    },
    {
        "asset": "Cybersecurity Credential Stack (CSAP, CSIS, CIOS, CNVP, CNSP)",
        "detail": (
            "Security is a top-of-mind objection in health IT procurement. Having "
            "certs removes a blocker that stalls many CSM and SE candidates."
        ),
        "talking_point": (
            "\"I can field HIPAA, HITRUST, and SOC 2 questions in a discovery call "
            "without looping in a security SME for basic questions.\""
        ),
    },
    {
        "asset": "Finance Degree",
        "detail": (
            "Enables ROI and TCO conversations — critical for enterprise deals where "
            "the economic buyer is a CFO or VP Finance, not just IT."
        ),
        "talking_point": (
            "\"I can build a business case alongside the customer's finance team, "
            "not just hand them a vendor ROI calculator.\""
        ),
    },
    {
        "asset": "Helpdesk / Frontline Customer Service Foundation",
        "detail": (
            "De-escalation, stakeholder communication under pressure, and technical "
            "translation skills are all practiced daily in a hospital helpdesk role."
        ),
        "talking_point": (
            "\"I've handled critical-system outages in a 24/7 hospital environment — "
            "I know how to stay calm, communicate clearly, and drive to resolution "
            "when the stakes are high.\""
        ),
    },
]

GAP_ANALYSIS_GAPS: list[dict] = [
    {
        "objection": "No direct SaaS or quota-carrying experience",
        "risk": "Hiring managers may filter on '2+ years SaaS CSM' requirements.",
        "rebuttal": (
            "\"The skills are fully transferable — I've managed technical "
            "relationships, driven adoption of clinical systems, and resolved "
            "escalations at scale. I'm targeting companies that hire for "
            "domain expertise + aptitude, not a title match.\""
        ),
        "mitigation": (
            "Target roles explicitly open to 'healthcare IT background' or "
            "'non-traditional CSM paths'. Use cover letters to reframe experience. "
            "Consider a contract/implementation role as a bridge if needed."
        ),
    },
    {
        "objection": "No quota or renewal history to cite",
        "risk": "SE and TCSM roles often ask for 'proven track record of hitting targets'.",
        "rebuttal": (
            "\"My metrics are ticket resolution time, CSAT scores, and system "
            "uptime — the operational equivalents of retention and expansion. "
            "I can quantify my impact even without a quota number.\""
        ),
        "mitigation": (
            "Document helpdesk KPIs (resolution rate, escalation rate, CSAT). "
            "Prepare a 'brag doc' with 3–5 quantified wins from hospital IT role."
        ),
    },
    {
        "objection": "Relocation to Nashville not until September 2026",
        "risk": "Some employers want local candidates immediately.",
        "rebuttal": (
            "\"I have a firm relocation date of September 2026. For fully remote "
            "roles, this is a non-issue. For hybrid roles, I'm happy to discuss "
            "a start date aligned with that timeline or periodic travel in the interim.\""
        ),
        "mitigation": (
            "Prioritize fully-remote roles. For Nashville-hybrid roles, "
            "start outreach 6 months before relocation to enter pipelines early. "
            "Be transparent upfront to avoid wasted time on both sides."
        ),
    },
    {
        "objection": "Salary target ($100K–$120K) may seem aggressive for a career pivot",
        "risk": "Entry-level CSM roles often start $70–$85K; SE roles start higher but require more technical depth.",
        "rebuttal": (
            "\"I'm not making a lateral move — I'm bringing 4 years of specialized "
            "domain knowledge that has direct revenue impact for healthcare IT vendors. "
            "The cert stack and degree combination supports a mid-level entry point.\""
        ),
        "mitigation": (
            "Target Series B+ companies and public companies with formalized CSM "
            "comp bands. Research Levels.fyi, Glassdoor, and Payscale for "
            "healthcare SaaS CSM comp before negotiating. OTE structure (base + "
            "variable) can bridge the gap even if base is slightly lower."
        ),
    },
]