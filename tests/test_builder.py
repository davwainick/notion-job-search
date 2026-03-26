"""
test_builder.py — Unit tests for the workspace builder.

All tests run entirely offline — the Notion API is mocked via
``unittest.mock``, so no token or internet connection is required.

Run with:
    pytest tests/
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, call, patch

import pytest

# ---------------------------------------------------------------------------
# Stub out notion_client before importing our modules
# ---------------------------------------------------------------------------
notion_client_stub = types.ModuleType("notion_client")

class _APIResponseError(Exception):
    def __init__(self, message="", code="", status=400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status

notion_client_stub.APIResponseError = _APIResponseError
notion_client_stub.APIErrorCode = MagicMock()
notion_client_stub.Client = MagicMock

sys.modules.setdefault("notion_client", notion_client_stub)

from notion_job_search.builder import (  # noqa: E402
    _rich_text,
    _paragraph,
    _heading_2,
    _heading_3,
    _bulleted_item,
    _divider,
    _callout,
    create_parent_page,
    create_database,
    patch_relations,
    seed_companies,
    create_gap_analysis,
    update_gap_analysis,
    build_workspace,
)
from notion_job_search.client import safe_api_call  # noqa: E402
from notion_job_search import config  # noqa: E402


# ===========================================================================
# Block factory helpers
# ===========================================================================

class TestRichText:
    def test_returns_list(self):
        assert isinstance(_rich_text("hello"), list)

    def test_correct_structure(self):
        result = _rich_text("world")
        assert result[0]["type"] == "text"
        assert result[0]["text"]["content"] == "world"

    def test_empty_string(self):
        assert _rich_text("")[0]["text"]["content"] == ""


class TestBlockFactories:
    def test_paragraph_type(self):
        assert _paragraph("x")["type"] == "paragraph"

    def test_heading_2_type(self):
        assert _heading_2("x")["type"] == "heading_2"

    def test_heading_3_type(self):
        assert _heading_3("x")["type"] == "heading_3"

    def test_bulleted_item_type(self):
        assert _bulleted_item("x")["type"] == "bulleted_list_item"

    def test_divider_type(self):
        assert _divider()["type"] == "divider"

    def test_callout_default_emoji(self):
        assert _callout("x")["callout"]["icon"]["emoji"] == "💡"

    def test_callout_custom_emoji(self):
        assert _callout("x", "📌")["callout"]["icon"]["emoji"] == "📌"


# ===========================================================================
# safe_api_call
# ===========================================================================

class TestSafeApiCall:
    def test_returns_value_on_success(self):
        fn = MagicMock(return_value={"id": "abc"})
        assert safe_api_call(fn, context="test") == {"id": "abc"}

    def test_raises_runtime_error_on_api_error(self):
        exc = _APIResponseError(message="bad token", code="unauthorized", status=401)
        fn = MagicMock(side_effect=exc)
        with pytest.raises(RuntimeError):
            safe_api_call(fn, context="unit test")

    def test_passes_args_and_kwargs(self):
        fn = MagicMock(return_value=None)
        safe_api_call(fn, "arg1", key="val", context="test")
        fn.assert_called_once_with("arg1", key="val")


# ===========================================================================
# create_parent_page
# ===========================================================================

class TestCreateParentPage:
    def _make_client(self, page_id="page-123"):
        client = MagicMock()
        client.pages.create.return_value = {"id": page_id}
        return client

    def test_returns_page_id(self):
        client = self._make_client("page-abc")
        assert create_parent_page(client, "root", "My Workspace") == "page-abc"

    def test_dry_run_returns_placeholder(self):
        client = self._make_client()
        result = create_parent_page(client, "root", dry_run=True)
        assert result == "dry-run-parent-page-id"
        client.pages.create.assert_not_called()

    def test_workspace_name_in_title(self):
        client = self._make_client()
        create_parent_page(client, "root", "Career Quest 2025")
        kwargs = client.pages.create.call_args[1]
        title_content = kwargs["properties"]["title"]["title"][0]["text"]["content"]
        assert title_content == "Career Quest 2025"

    def test_default_workspace_name(self):
        client = self._make_client()
        create_parent_page(client, "root")
        kwargs = client.pages.create.call_args[1]
        title_content = kwargs["properties"]["title"]["title"][0]["text"]["content"]
        assert title_content == "Job Search HQ"


# ===========================================================================
# create_database
# ===========================================================================

class TestCreateDatabase:
    def _make_client(self, db_id="db-123"):
        client = MagicMock()
        client.request.return_value = {"id": db_id}
        return client

    def test_returns_db_id(self):
        client = self._make_client("db-abc")
        result = create_database(client, "parent", "companies", config.SCHEMA_COMPANIES)
        assert result == "db-abc"

    def test_dry_run_returns_placeholder(self):
        client = self._make_client()
        result = create_database(
            client, "parent", "companies", config.SCHEMA_COMPANIES, dry_run=True
        )
        assert result == "dry-run-companies-id"
        client.request.assert_not_called()

    def test_uses_client_request_not_databases_create(self):
        """Verify we call client.request() to bypass the SDK pick() whitelist."""
        client = self._make_client()
        create_database(client, "parent", "companies", config.SCHEMA_COMPANIES)
        client.request.assert_called_once()
        call_kwargs = client.request.call_args[1]
        assert call_kwargs["path"] == "databases"
        assert call_kwargs["method"] == "POST"
        assert "properties" in call_kwargs["body"]

    def test_no_is_inline_in_body(self):
        """is_inline was removed — verify it is not sent."""
        client = self._make_client()
        create_database(client, "parent", "companies", config.SCHEMA_COMPANIES)
        body = client.request.call_args[1]["body"]
        assert "is_inline" not in body


# ===========================================================================
# patch_relations
# ===========================================================================

class TestPatchRelations:
    def _db_ids(self):
        return {
            "companies": "c-id",
            "job_postings": "jp-id",
            "contacts": "con-id",
            "outreach_log": "ol-id",
        }

    def test_dry_run_no_api_calls(self):
        client = MagicMock()
        patch_relations(client, self._db_ids(), dry_run=True)
        client.request.assert_not_called()

    def test_patches_seven_relations(self):
        client = MagicMock()
        client.request.return_value = {}
        patch_relations(client, self._db_ids())
        assert client.request.call_count == 7

    def test_uses_patch_method(self):
        client = MagicMock()
        client.request.return_value = {}
        patch_relations(client, self._db_ids())
        for c in client.request.call_args_list:
            assert c[1]["method"] == "PATCH"


# ===========================================================================
# seed_companies
# ===========================================================================

class TestSeedCompanies:
    def _db_ids(self):
        return {
            "companies": "c-id",
            "job_postings": "jp-id",
            "contacts": "con-id",
            "outreach_log": "ol-id",
        }

    def test_dry_run_no_api_calls(self):
        client = MagicMock()
        seed_companies(client, self._db_ids(), dry_run=True)
        client.pages.create.assert_not_called()

    def test_inserts_three_companies(self):
        client = MagicMock()
        client.pages.create.return_value = {"id": "row"}
        seed_companies(client, self._db_ids())
        assert client.pages.create.call_count == 3

    def test_each_row_has_company_name_title(self):
        client = MagicMock()
        client.pages.create.return_value = {"id": "row"}
        seed_companies(client, self._db_ids())
        for c in client.pages.create.call_args_list:
            assert "Company Name" in c[1]["properties"]

    def test_generic_company_names(self):
        """Seed companies should not contain any personalized names."""
        names = [c["name"] for c in config.SEED_COMPANIES]
        assert "Acme Corp" in names
        assert "Example Inc" in names
        assert "Sample Co" in names

    def test_seed_companies_count(self):
        assert len(config.SEED_COMPANIES) == 3

    def test_seed_companies_required_fields(self):
        required = {
            "name", "platform", "tier", "status", "hq", "remote",
            "size", "funding", "open_role", "why_fit", "website",
            "careers", "linkedin", "next_action",
        }
        for company in config.SEED_COMPANIES:
            missing = required - set(company.keys())
            assert not missing, f"'{company.get('name')}' missing: {missing}"


# ===========================================================================
# create_gap_analysis — template version
# ===========================================================================

class TestCreateGapAnalysis:
    def test_dry_run_returns_placeholder(self):
        client = MagicMock()
        result = create_gap_analysis(client, "parent", dry_run=True)
        assert result == "dry-run-gap-analysis-id"
        client.pages.create.assert_not_called()

    def test_returns_page_id(self):
        client = MagicMock()
        client.pages.create.return_value = {"id": "gap-id"}
        assert create_gap_analysis(client, "parent") == "gap-id"

    def test_page_has_children(self):
        client = MagicMock()
        client.pages.create.return_value = {"id": "gap-id"}
        create_gap_analysis(client, "parent")
        assert len(client.pages.create.call_args[1]["children"]) > 0

    def test_page_icon_is_brain(self):
        client = MagicMock()
        client.pages.create.return_value = {"id": "gap-id"}
        create_gap_analysis(client, "parent")
        assert client.pages.create.call_args[1]["icon"]["emoji"] == "🧠"

    def test_no_personal_content_in_template(self):
        """The template page must not contain any hardcoded personal data."""
        client = MagicMock()
        client.pages.create.return_value = {"id": "gap-id"}
        create_gap_analysis(client, "parent")
        block_str = str(client.pages.create.call_args[1]["children"])
        # These were in the old personalised version — must not appear
        assert "Stony Brook" not in block_str
        assert "ITIL" not in block_str
        assert "Nashville" not in block_str


# ===========================================================================
# update_gap_analysis
# ===========================================================================

class TestUpdateGapAnalysis:
    def _make_client(self):
        client = MagicMock()
        client.blocks.children.list.return_value = {"results": []}
        client.blocks.children.append.return_value = {}
        return client

    def test_empty_lists_returns_early(self):
        client = self._make_client()
        update_gap_analysis(client, "gap-id", [], [])
        client.blocks.children.list.assert_not_called()
        client.blocks.children.append.assert_not_called()

    def test_appends_strength_blocks(self):
        client = self._make_client()
        strengths = [{"strength": "Domain expertise", "talking_point": "I know the space."}]
        update_gap_analysis(client, "gap-id", strengths, [])
        client.blocks.children.append.assert_called()
        children = client.blocks.children.append.call_args[1]["children"]
        block_str = str(children)
        assert "Domain expertise" in block_str

    def test_appends_gap_blocks(self):
        client = self._make_client()
        gaps = [{"objection": "No SaaS exp", "rebuttal": "Skills transfer.", "mitigation": "Target open roles."}]
        update_gap_analysis(client, "gap-id", [], gaps)
        client.blocks.children.append.assert_called()
        children = client.blocks.children.append.call_args[1]["children"]
        block_str = str(children)
        assert "No SaaS exp" in block_str

    def test_deletes_existing_blocks_first(self):
        client = MagicMock()
        client.blocks.children.list.return_value = {
            "results": [{"id": "block-1"}, {"id": "block-2"}]
        }
        client.blocks.delete.return_value = {}
        client.blocks.children.append.return_value = {}
        strengths = [{"strength": "Test", "talking_point": ""}]
        update_gap_analysis(client, "gap-id", strengths, [])
        assert client.blocks.delete.call_count == 2

    def test_skips_empty_strength_entries(self):
        client = self._make_client()
        strengths = [
            {"strength": "", "talking_point": "some point"},
            {"strength": "Real strength", "talking_point": ""},
        ]
        update_gap_analysis(client, "gap-id", strengths, [])
        children = client.blocks.children.append.call_args[1]["children"]
        block_str = str(children)
        assert "Real strength" in block_str
        assert "some point" not in block_str


# ===========================================================================
# build_workspace
# ===========================================================================

class TestBuildWorkspace:
    def _make_client(self):
        client = MagicMock()
        client.pages.create.return_value = {"id": "page-id"}
        client.request.return_value = {"id": "db-id"}
        return client

    def test_returns_required_keys(self):
        client = self._make_client()
        result = build_workspace(client, "root", dry_run=True)
        expected = {
            "parent_page_id", "gap_analysis_id", "notion_url",
            "companies", "job_postings", "contacts", "outreach_log",
        }
        assert expected == set(result.keys())

    def test_notion_url_present_and_hyphenless(self):
        client = self._make_client()
        client.pages.create.return_value = {"id": "abc-123-def"}
        result = build_workspace(client, "root")
        assert "notion_url" in result
        assert "-" not in result["notion_url"].replace("https://notion.so/", "")

    def test_dry_run_notion_url_uses_placeholder(self):
        client = self._make_client()
        result = build_workspace(client, "root", dry_run=True)
        assert result["notion_url"].startswith("https://notion.so/")

    def test_workspace_name_passed_to_parent_page(self):
        client = self._make_client()
        build_workspace(client, "root", "Career HQ 2025")
        kwargs = client.pages.create.call_args_list[0][1]
        title = kwargs["properties"]["title"]["title"][0]["text"]["content"]
        assert title == "Career HQ 2025"

    def test_default_workspace_name(self):
        client = self._make_client()
        build_workspace(client, "root")
        kwargs = client.pages.create.call_args_list[0][1]
        title = kwargs["properties"]["title"]["title"][0]["text"]["content"]
        assert title == "Job Search HQ"

    def test_gap_analysis_id_in_result(self):
        client = self._make_client()
        result = build_workspace(client, "root")
        assert "gap_analysis_id" in result
        assert result["gap_analysis_id"] != ""

    def test_seed_data_calls_pages_create_extra_times(self):
        client = self._make_client()
        build_workspace(client, "root", seed_data=True)
        # parent page + 3 seed companies + gap analysis = at least 5
        assert client.pages.create.call_count >= 5

    def test_no_seed_data_by_default(self):
        client = self._make_client()
        build_workspace(client, "root", seed_data=False)
        # parent page + gap analysis = exactly 2
        assert client.pages.create.call_count == 2

    def test_progress_callback_called(self):
        client = self._make_client()
        messages = []
        build_workspace(client, "root", progress_callback=messages.append)
        assert len(messages) > 0

    def test_progress_callback_none_is_safe(self):
        client = self._make_client()
        # Should not raise even with no callback
        build_workspace(client, "root", progress_callback=None)


# ===========================================================================
# Config schema sanity
# ===========================================================================

class TestConfig:
    def test_all_db_names_present(self):
        for key in ("companies", "job_postings", "contacts", "outreach_log"):
            assert key in config.DB_NAMES

    def test_schemas_have_exactly_one_title(self):
        for schema in (
            config.SCHEMA_COMPANIES,
            config.SCHEMA_JOB_POSTINGS,
            config.SCHEMA_CONTACTS,
            config.SCHEMA_OUTREACH_LOG,
        ):
            titles = [k for k, v in schema.items() if "title" in v]
            assert len(titles) == 1

    def test_no_commas_in_select_options(self):
        for schema in (
            config.SCHEMA_COMPANIES,
            config.SCHEMA_JOB_POSTINGS,
            config.SCHEMA_CONTACTS,
            config.SCHEMA_OUTREACH_LOG,
        ):
            for prop, defn in schema.items():
                if "select" in defn:
                    for opt in defn["select"]["options"]:
                        assert "," not in opt["name"], (
                            f"Comma in option '{opt['name']}' of property '{prop}'"
                        )

    def test_notion_api_version_pinned(self):
        assert config.NOTION_API_VERSION == "2022-06-28"