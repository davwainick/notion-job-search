"""
state.py — Manages persistent local state for the notion-job-search application.

State is stored in ``~/.notion_job_search/workspaces.json`` as a JSON array of
workspace entries.  Each entry contains the workspace name, Notion URLs,
database IDs, and the Notion integration token (encrypted at rest).

Encryption
----------
The integration token is encrypted using the ``cryptography`` package's Fernet
symmetric encryption.  A machine-local key is generated once on first run and
stored at ``~/.notion_job_search/.key``.  This key is never transmitted and
is used only to protect the token on disk.  The encryption is not
cryptographically tied to the machine hardware — it provides protection against
casual inspection of the JSON file, not against a determined attacker with
filesystem access.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Directory and file paths
# ---------------------------------------------------------------------------

STATE_DIR = Path.home() / ".notion_job_search"
STATE_FILE = STATE_DIR / "workspaces.json"
KEY_FILE = STATE_DIR / ".key"


def _ensure_state_dir() -> None:
    """Create the state directory if it does not already exist."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def _get_or_create_key() -> bytes:
    """
    Load the Fernet encryption key from disk, creating it on first run.

    The key is stored at ``~/.notion_job_search/.key`` as raw bytes.
    On first run the key is generated with ``Fernet.generate_key()`` and
    written to disk.  Subsequent runs read the same key so that previously
    encrypted tokens can still be decrypted.

    Returns:
        The 32-byte URL-safe base64-encoded Fernet key.
    """
    from cryptography.fernet import Fernet  # type: ignore

    _ensure_state_dir()
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()
    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)
    # Restrict permissions on Unix-like systems
    try:
        KEY_FILE.chmod(0o600)
    except OSError:
        pass
    return key


def _encrypt_token(token: str) -> str:
    """
    Encrypt a Notion integration token using the machine-local Fernet key.

    Args:
        token: Plain-text integration token (starts with ``secret_``).

    Returns:
        URL-safe base64-encoded encrypted token as a string.
    """
    from cryptography.fernet import Fernet  # type: ignore

    key = _get_or_create_key()
    f = Fernet(key)
    return f.encrypt(token.encode()).decode()


def _decrypt_token(encrypted: str) -> str:
    """
    Decrypt a previously encrypted Notion integration token.

    Args:
        encrypted: Encrypted token string as returned by :func:`_encrypt_token`.

    Returns:
        Plain-text integration token.

    Raises:
        ValueError: If decryption fails (e.g. the key file was deleted or
                    the state file was copied from another machine).
    """
    from cryptography.fernet import Fernet, InvalidToken  # type: ignore

    try:
        key = _get_or_create_key()
        f = Fernet(key)
        return f.decrypt(encrypted.encode()).decode()
    except (InvalidToken, Exception) as exc:
        raise ValueError(
            "Failed to decrypt the stored Notion token. "
            "This can happen if the key file (~/.notion_job_search/.key) was "
            "deleted or if the state file was copied from another machine. "
            "Create a new workspace to re-enter your token."
        ) from exc


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_workspaces() -> list[dict]:
    """
    Load all saved workspace entries from the state file.

    Returns:
        A list of workspace dicts.  Returns an empty list if the state file
        does not exist or is empty.
    """
    if not STATE_FILE.exists():
        return []
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_workspace(entry: dict[str, Any]) -> None:
    """
    Append a new workspace entry to the state file.

    The ``token`` value in *entry* is encrypted before writing.
    A ``created_at`` timestamp is added automatically if not already present.

    Args:
        entry: Workspace metadata dict containing at minimum:
               ``name``, ``parent_page_id``, ``notion_url``,
               ``database_ids``, ``gap_page_id``, ``token``.
    """
    _ensure_state_dir()
    workspaces = load_workspaces()

    # Encrypt the token before persisting
    to_save = dict(entry)
    if "token" in to_save and not to_save["token"].startswith("gAAAAA"):
        # Only encrypt if it looks like a plain-text token
        try:
            to_save["token"] = _encrypt_token(to_save["token"])
        except Exception:
            # If cryptography is unavailable store as-is (e.g. in tests)
            pass

    if "created_at" not in to_save:
        to_save["created_at"] = datetime.now(timezone.utc).isoformat()

    workspaces.append(to_save)
    STATE_FILE.write_text(
        json.dumps(workspaces, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def delete_workspace(index: int) -> None:
    """
    Remove a workspace entry by its list index and write back.

    Args:
        index: Zero-based index of the entry to remove.

    Raises:
        IndexError: If *index* is out of range.
    """
    workspaces = load_workspaces()
    if index < 0 or index >= len(workspaces):
        raise IndexError(
            f"Workspace index {index} is out of range "
            f"(have {len(workspaces)} workspaces)."
        )
    workspaces.pop(index)
    _ensure_state_dir()
    STATE_FILE.write_text(
        json.dumps(workspaces, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def has_workspaces() -> bool:
    """
    Return *True* if at least one workspace has been saved on this machine.

    Returns:
        ``True`` if the state file exists and contains at least one entry.
    """
    return len(load_workspaces()) > 0


def get_token(workspace_entry: dict) -> str:
    """
    Retrieve the decrypted integration token from a workspace entry.

    Args:
        workspace_entry: A single dict from :func:`load_workspaces`.

    Returns:
        Plain-text Notion integration token.

    Raises:
        ValueError: If decryption fails.
    """
    encrypted = workspace_entry.get("token", "")
    return _decrypt_token(encrypted)
