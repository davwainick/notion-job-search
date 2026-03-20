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
from unittest.mock import MagicMock, patch, call

import pytest

# ---------------------------------------------------------------------------
# Stub out notion_client before importing our modules, so tests don't require
# the package to be installed.
# ---------------------------------------------------------------------------
notion_client_stub = types.ModuleType("notion_client")

class _APIResponseError(Exception):
    """Minimal stub matching the real APIResponseError interface."""
    def __init__(self, message="", code="", status=400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status

notion_client_stub.APIResponseError = _APIResponseError
notion_client_stub.APIErrorCode = MagicMock()
notion_client_stub.Client = MagicMock

sys.modules.setdefault("notion_client", notion_client_stub)

# Now safe to import our modules.
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
    build_workspace,
)
from notion_job_search.client import safe_api_call  # noqa: E402
from notion_job_search import config  # noqa: E402


# ===========================================================================
# Helper / block factory tests
# ===========================================================================

class TestRichText:
    def test_returns_list(self):
        result = _rich_text("hello")
        assert isinstance(result, list)
        assert len(result) == 1

    def test_correct_structure(self):
        result = _rich_text("world")
        assert result[0]["type"] == "text"
        assert result[0]["text"]["content"] == "world"

    def test_empty_string(self):
        result = _rich_text("")
        assert result[0]["text"]["content"] == ""


class TestBlockFactories:
    def test_paragraph_type(self):
        block = _paragraph("test")
        assert block["type"] == "paragraph"
        assert block["object"] == "block"

    def test_heading_2_type(self):
        block = _heading_2("Section")
        assert block["type"] == "heading_2"

    def test_heading_3_type(self):
        block = _heading_3("Subsection")
        assert block["type"] == "heading_3"

    def test_bulleted_item_type(self):
        block = _bulleted_item("item")
        assert block["type"] == "bulleted_list_item"

    def test_divider_type(self):
        block = _divider()
        assert block["type"] == "divider"

    def test_callout_default_emoji(self):
        block = _callout("tip")
        assert block["type"] == "callout"
        assert block["callout"]["icon"]["emoji"] == "💡"

    def test_callout_custom_emoji(self):
        block = _callout("note", "📌")
        assert block["callout"]["icon"]["emoji"] == "📌"


# ===========================================================================
# safe_api_call tests
# ===========================================================================

class TestSafeApiCall:
    def test_returns_value_on_success(self):
        fn = MagicMock(return_value={"id": "abc"})
        result = safe_api_call(fn, context="test")
        assert result == {"id": "abc"}

    def test_raises_runtime_error_on_api_error(self):
        exc = _APIResponseError(message="bad token", code="unauthorized", status=401)
        fn = MagicMock(side_effect=exc)
        with pytest.raises(RuntimeError, match="bad token"):
            safe_api_call(fn, context="unit test")

    def test_error_message_includes_context(self):
        exc = _APIResponseError(message="not found", code="object_not_found", status=404)
        fn = MagicMock(side_effect=exc)
        with pytest.raises(RuntimeError, match="unit test context"):
            safe_api_call(fn, context="unit test context")

    def test_passes_args_and_kwargs(self):
        fn = MagicMock(return_value=None)
        safe_api_call(fn, "arg1", key="val", context="test")
        fn.assert_called_once_with("arg1", key="val")


# ===========================================================================
# create_parent_page tests
# ===========================================================================

class TestCreateParentPage:
    def _make_client(self, page_id="page-123"):
        client = MagicMock()
        client.pages.create.return_value = {"id": page_id}
        return client

    def test_returns_page_id(self):
        client = self._make_client("page-abc")
        result = create_parent_page(client, "root-id")
        assert result == "page-abc"

    def test_dry_run_returns_placeholder(self):
        client = self._make_client()
        result = create_parent_page(client, "root-id", dry_run=True)
        assert result == "dry-run-parent-page-id"
        client.pages.create.assert_not_called()

    def test_payload_includes_emoji_icon(self):
        client = self._make_client()
        create_parent_page(client, "root-id")
        call_kwargs = client.pages.create.call_args[1]
        assert call_kwargs["icon"]["emoji"] == "🗂️"

    def test_payload_includes_correct_parent(self):
        client = self._make_client()
        create_parent_page(client, "root-xyz")
        call_kwargs = client.pages.create.call_args[1]
        assert call_kwargs["parent"]["page_id"] == "root-xyz"


# ===========================================================================
# create_database tests
# ===========================================================================

class TestCreateDatabase:
    def _make_client(self, db_id="db-123"):
        client = MagicMock()
        client.databases.create.return_value = {"id": db_id}
        return client

    def test_returns_db_id(self):
        client = self._make_client("db-abc")
        result = create_database(client, "parent-id", "companies", config.SCHEMA_COMPANIES)
        assert result == "db-abc"

    def test_dry_run_returns_placeholder(self):
        client = self._make_client()
        result = create_database(
            client, "parent-id", "companies", config.SCHEMA_COMPANIES, dry_run=True
        )
        assert result == "dry-run-companies-id"
        client.databases.create.assert_not_called()

    def test_all_db_keys_produce_correct_placeholders(self):
        client = self._make_client()
        for key in ("companies", "job_postings", "contacts", "outreach_log"):
            result = create_database(
                client, "parent-id", key, {}, dry_run=True
            )
            assert result == f"dry-run-{key}-id"


# ===========================================================================
# patch_relations tests
# ===========================================================================

class TestPatchRelations:
    def _make_db_ids(self):
        return {
            "companies":    "c-id",
            "job_postings": "jp-id",
            "contacts":     "con-id",
            "outreach_log": "ol-id",
        }

    def test_dry_run_does_not_call_api(self):
        client = MagicMock()
        patch_relations(client, self._make_db_ids(), dry_run=True)
        client.databases.update.assert_not_called()

    def test_patches_correct_number_of_relations(self):
        client = MagicMock()
        client.databases.update.return_value = {}
        patch_relations(client, self._make_db_ids())
        # 7 relation entries defined in builder.py
        assert client.databases.update.call_count == 7

    def test_relation_payload_structure(self):
        client = MagicMock()
        client.databases.update.return_value = {}
        patch_relations(client, self._make_db_ids())
        # Grab the first call's positional arg and kwargs
        first_call = client.databases.update.call_args_list[0]
        kwargs = first_call[1]
        props = kwargs["properties"]
        prop_name = list(props.keys())[0]
        assert "relation" in props[prop_name]
        assert "database_id" in props[prop_name]["relation"]


# ===========================================================================
# seed_companies tests
# ===========================================================================

class TestSeedCompanies:
    def _make_db_ids(self):
        return {
            "companies":    "c-id",
            "job_postings": "jp-id",
            "contacts":     "con-id",
            "outreach_log": "ol-id",
        }

    def test_dry_run_does_not_call_api(self):
        client = MagicMock()
        seed_companies(client, self._make_db_ids(), dry_run=True)
        client.pages.create.assert_not_called()

    def test_inserts_five_companies(self):
        client = MagicMock()
        client.pages.create.return_value = {"id": "row-id"}
        seed_companies(client, self._make_db_ids())
        assert client.pages.create.call_count == 5

    def test_each_row_has_title_property(self):
        client = MagicMock()
        client.pages.create.return_value = {"id": "row-id"}
        seed_companies(client, self._make_db_ids())
        for c in client.pages.create.call_args_list:
            props = c[1]["properties"]
            assert "Company Name" in props
            assert "title" in props["Company Name"]


# ===========================================================================
# create_gap_analysis tests
# ===========================================================================

class TestCreateGapAnalysis:
    def test_dry_run_returns_placeholder(self):
        client = MagicMock()
        result = create_gap_analysis(client, "parent-id", dry_run=True)
        assert result == "dry-run-gap-analysis-id"
        client.pages.create.assert_not_called()

    def test_returns_page_id(self):
        client = MagicMock()
        client.pages.create.return_value = {"id": "gap-page-id"}
        result = create_gap_analysis(client, "parent-id")
        assert result == "gap-page-id"

    def test_page_has_children_blocks(self):
        client = MagicMock()
        client.pages.create.return_value = {"id": "gap-page-id"}
        create_gap_analysis(client, "parent-id")
        kwargs = client.pages.create.call_args[1]
        assert len(kwargs["children"]) > 0

    def test_page_icon_is_brain_emoji(self):
        client = MagicMock()
        client.pages.create.return_value = {"id": "gap-page-id"}
        create_gap_analysis(client, "parent-id")
        kwargs = client.pages.create.call_args[1]
        assert kwargs["icon"]["emoji"] == "🧠"

    def test_all_strengths_appear_in_blocks(self):
        """Each strength should generate at least one block mentioning the asset."""
        client = MagicMock()
        client.pages.create.return_value = {"id": "gap-id"}
        create_gap_analysis(client, "parent-id")
        kwargs = client.pages.create.call_args[1]
        block_text = str(kwargs["children"])
        for item in config.GAP_ANALYSIS_STRENGTHS:
            assert item["asset"] in block_text

    def test_all_gaps_appear_in_blocks(self):
        """Each gap/objection should generate at least one block."""
        client = MagicMock()
        client.pages.create.return_value = {"id": "gap-id"}
        create_gap_analysis(client, "parent-id")
        kwargs = client.pages.create.call_args[1]
        block_text = str(kwargs["children"])
        for item in config.GAP_ANALYSIS_GAPS:
            # The objection string appears in a heading_3 block
            assert item["objection"] in block_text


# ===========================================================================
# build_workspace integration test
# ===========================================================================

class TestBuildWorkspace:
    def _make_client(self):
        client = MagicMock()
        client.pages.create.return_value = {"id": "page-id"}
        client.databases.create.return_value = {"id": "db-id"}
        client.databases.update.return_value = {}
        return client

    def test_dry_run_returns_dict_with_all_keys(self):
        client = self._make_client()
        result = build_workspace(client, "root", dry_run=True)
        expected_keys = {
            "parent_page_id", "gap_analysis_id",
            "companies", "job_postings", "contacts", "outreach_log",
        }
        assert expected_keys == set(result.keys())

    def test_with_seed_data_calls_pages_create_extra_times(self):
        client = self._make_client()
        build_workspace(client, "root", seed_data=True)
        # At least 1 (parent) + 5 (companies) + 1 (gap analysis) = 7 page creations
        assert client.pages.create.call_count >= 7

    def test_without_seed_data_does_not_insert_rows(self):
        client = self._make_client()
        build_workspace(client, "root", seed_data=False)
        # Only 2 page creates: parent page + gap analysis
        assert client.pages.create.call_count == 2


# ===========================================================================
# Config sanity checks
# ===========================================================================

class TestConfig:
    def test_all_db_names_defined(self):
        for key in ("companies", "job_postings", "contacts", "outreach_log"):
            assert key in config.DB_NAMES

    def test_schemas_have_title_property(self):
        for schema in (
            config.SCHEMA_COMPANIES,
            config.SCHEMA_JOB_POSTINGS,
            config.SCHEMA_CONTACTS,
            config.SCHEMA_OUTREACH_LOG,
        ):
            title_props = [k for k, v in schema.items() if "title" in v]
            assert len(title_props) == 1, (
                f"Schema should have exactly one title property, found: {title_props}"
            )

    def test_seed_companies_count(self):
        assert len(config.SEED_COMPANIES) == 5

    def test_seed_companies_have_required_fields(self):
        required = {"name", "platform", "tier", "status", "hq", "remote",
                    "size", "funding", "open_role", "why_fit", "website",
                    "careers", "linkedin", "next_action"}
        for company in config.SEED_COMPANIES:
            missing = required - set(company.keys())
            assert not missing, f"Company '{company.get('name')}' missing fields: {missing}"

    def test_gap_analysis_strengths_have_required_fields(self):
        for item in config.GAP_ANALYSIS_STRENGTHS:
            assert "asset" in item
            assert "detail" in item
            assert "talking_point" in item

    def test_gap_analysis_gaps_have_required_fields(self):
        for item in config.GAP_ANALYSIS_GAPS:
            assert "objection" in item
            assert "risk" in item
            assert "rebuttal" in item
            assert "mitigation" in item

    def test_notion_api_version_pinned(self):
        assert config.NOTION_API_VERSION == "2022-06-28"
