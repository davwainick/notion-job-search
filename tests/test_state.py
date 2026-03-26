"""
test_state.py — Unit tests for the state management module.

All file I/O is redirected to pytest's tmp_path fixture so the real
~/.notion_job_search/ directory is never touched.

Fernet encryption is mocked so these tests do not require the
``cryptography`` package to be installed.

Run with:
    pytest tests/
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _patch_state_paths(tmp_path, monkeypatch):
    """
    Redirect all state file reads/writes to a temporary directory.

    This fixture patches the module-level path constants in ``state.py``
    before each test so no files are written to the user's home directory.
    """
    import notion_job_search.state as state_mod

    fake_dir = tmp_path / "notion_job_search"
    fake_dir.mkdir()
    monkeypatch.setattr(state_mod, "STATE_DIR", fake_dir)
    monkeypatch.setattr(state_mod, "STATE_FILE", fake_dir / "workspaces.json")
    monkeypatch.setattr(state_mod, "KEY_FILE", fake_dir / ".key")


@pytest.fixture()
def _mock_crypto(monkeypatch):
    """
    Replace Fernet encryption with identity functions.

    This allows state tests to run without the cryptography package and
    without worrying about key management.
    """
    import notion_job_search.state as state_mod

    monkeypatch.setattr(state_mod, "_encrypt_token", lambda t: f"enc:{t}")
    monkeypatch.setattr(state_mod, "_decrypt_token", lambda t: t.removeprefix("enc:"))


# ---------------------------------------------------------------------------
# load_workspaces
# ---------------------------------------------------------------------------

class TestLoadWorkspaces:
    def test_returns_empty_list_when_no_file(self):
        from notion_job_search.state import load_workspaces
        assert load_workspaces() == []

    def test_returns_workspaces_from_file(self, tmp_path):
        from notion_job_search import state as state_mod
        data = [{"name": "WS1"}, {"name": "WS2"}]
        state_mod.STATE_FILE.write_text(json.dumps(data), encoding="utf-8")
        result = state_mod.load_workspaces()
        assert len(result) == 2
        assert result[0]["name"] == "WS1"

    def test_returns_empty_list_on_corrupt_json(self, tmp_path):
        from notion_job_search import state as state_mod
        state_mod.STATE_FILE.write_text("not json!!!", encoding="utf-8")
        assert state_mod.load_workspaces() == []

    def test_returns_empty_list_on_non_list_json(self, tmp_path):
        from notion_job_search import state as state_mod
        state_mod.STATE_FILE.write_text('{"key": "val"}', encoding="utf-8")
        assert state_mod.load_workspaces() == []


# ---------------------------------------------------------------------------
# save_workspace
# ---------------------------------------------------------------------------

class TestSaveWorkspace:
    def test_saves_single_entry(self, _mock_crypto):
        from notion_job_search.state import save_workspace, load_workspaces
        save_workspace({"name": "Test WS", "token": "secret_abc"})
        workspaces = load_workspaces()
        assert len(workspaces) == 1
        assert workspaces[0]["name"] == "Test WS"

    def test_appends_multiple_entries(self, _mock_crypto):
        from notion_job_search.state import save_workspace, load_workspaces
        save_workspace({"name": "WS1", "token": "t1"})
        save_workspace({"name": "WS2", "token": "t2"})
        workspaces = load_workspaces()
        assert len(workspaces) == 2

    def test_created_at_added_automatically(self, _mock_crypto):
        from notion_job_search.state import save_workspace, load_workspaces
        save_workspace({"name": "WS", "token": "t"})
        ws = load_workspaces()[0]
        assert "created_at" in ws
        assert ws["created_at"]  # non-empty

    def test_token_is_encrypted(self, _mock_crypto):
        from notion_job_search.state import save_workspace, load_workspaces
        save_workspace({"name": "WS", "token": "secret_mytoken"})
        raw = load_workspaces()[0]
        # The mock prefixes with "enc:" so it should not equal the original
        assert raw["token"] != "secret_mytoken"
        assert raw["token"].startswith("enc:")

    def test_preserves_existing_created_at(self, _mock_crypto):
        from notion_job_search.state import save_workspace, load_workspaces
        save_workspace({"name": "WS", "token": "t", "created_at": "2024-01-01T00:00:00+00:00"})
        ws = load_workspaces()[0]
        assert ws["created_at"] == "2024-01-01T00:00:00+00:00"


# ---------------------------------------------------------------------------
# delete_workspace
# ---------------------------------------------------------------------------

class TestDeleteWorkspace:
    def test_deletes_by_index(self, _mock_crypto):
        from notion_job_search.state import save_workspace, delete_workspace, load_workspaces
        save_workspace({"name": "WS1", "token": "t1"})
        save_workspace({"name": "WS2", "token": "t2"})
        delete_workspace(0)
        remaining = load_workspaces()
        assert len(remaining) == 1
        assert remaining[0]["name"] == "WS2"

    def test_deletes_last_entry(self, _mock_crypto):
        from notion_job_search.state import save_workspace, delete_workspace, load_workspaces
        save_workspace({"name": "WS1", "token": "t1"})
        delete_workspace(0)
        assert load_workspaces() == []

    def test_raises_on_out_of_range_index(self, _mock_crypto):
        from notion_job_search.state import save_workspace, delete_workspace
        save_workspace({"name": "WS1", "token": "t1"})
        with pytest.raises(IndexError):
            delete_workspace(5)

    def test_raises_on_empty_list(self):
        from notion_job_search.state import delete_workspace
        with pytest.raises(IndexError):
            delete_workspace(0)


# ---------------------------------------------------------------------------
# has_workspaces
# ---------------------------------------------------------------------------

class TestHasWorkspaces:
    def test_false_when_no_file(self):
        from notion_job_search.state import has_workspaces
        assert has_workspaces() is False

    def test_true_after_saving(self, _mock_crypto):
        from notion_job_search.state import save_workspace, has_workspaces
        save_workspace({"name": "WS", "token": "t"})
        assert has_workspaces() is True

    def test_false_after_deleting_all(self, _mock_crypto):
        from notion_job_search.state import save_workspace, delete_workspace, has_workspaces
        save_workspace({"name": "WS", "token": "t"})
        delete_workspace(0)
        assert has_workspaces() is False


# ---------------------------------------------------------------------------
# get_token
# ---------------------------------------------------------------------------

class TestGetToken:
    def test_decrypts_token(self, _mock_crypto):
        from notion_job_search.state import save_workspace, load_workspaces, get_token
        save_workspace({"name": "WS", "token": "secret_real_token"})
        ws = load_workspaces()[0]
        assert get_token(ws) == "secret_real_token"
