"""
client.py — Thin wrapper around ``notion-client`` that centralises auth and
version headers, and surfaces readable error messages on failure.

Using the official ``notion-client`` SDK (rather than raw ``requests`` calls)
gives us automatic retry logic, cleaner error types, and more maintainable
code — all of which matter when this project is read by technical reviewers.
"""

from __future__ import annotations

import os

from notion_client import Client, APIResponseError  # type: ignore

from .config import NOTION_API_VERSION


def get_client(token: str | None = None) -> Client:
    """
    Instantiate and return an authenticated Notion API client.

    The client is pre-configured with the pinned ``Notion-Version`` header
    (``2022-06-28``) so all calls in this project are shielded from the
    breaking changes introduced in the September 2025 API version.

    Args:
        token: Notion integration token.  If *None*, the value of the
               ``NOTION_TOKEN`` environment variable is used.

    Returns:
        An authenticated :class:`notion_client.Client` instance.

    Raises:
        ValueError: If no token is available from either source.
    """
    resolved_token = token or os.getenv("NOTION_TOKEN")
    if not resolved_token:
        raise ValueError(
            "No Notion token found.  Set NOTION_TOKEN in your .env file "
            "or pass --token on the command line."
        )

    return Client(
        auth=resolved_token,
        notion_version=NOTION_API_VERSION,
    )


def safe_api_call(fn, *args, context: str = "", **kwargs):
    """
    Execute a Notion SDK call and surface a human-readable error on failure.

    Wraps any :class:`notion_client.APIResponseError` and re-raises it as a
    ``RuntimeError`` with a message that includes the HTTP status, Notion error
    code, and the operation context string supplied by the caller.

    The stable public interface of APIResponseError across all SDK versions:
      - ``exc.code``       — Notion error code string
      - ``exc.response``   — httpx Response object (has .status_code)
      - ``str(exc)``       — human-readable error message

    We deliberately avoid ``exc.message``, ``exc.status``, and ``exc.body``
    because their presence varies by SDK version and accessing a missing
    attribute on this class raises AttributeError rather than returning None.

    Args:
        fn:      Any callable that makes a Notion API call.
        *args:   Positional arguments forwarded to *fn*.
        context: Short description of what was being attempted.
        **kwargs: Keyword arguments forwarded to *fn*.

    Returns:
        The return value of *fn*.

    Raises:
        RuntimeError: Wrapping the original APIResponseError with context.
    """
    try:
        return fn(*args, **kwargs)
    except APIResponseError as exc:
        # .code is stable across all SDK versions
        code = exc.code  # noqa: B009

        # .response is the underlying httpx.Response object
        try:
            status = exc.response.status_code
        except AttributeError:
            status = "unknown"

        # str(exc) is always the Notion API error message text
        message = str(exc)

        msg = (
            f"Notion API error while {context or 'executing request'}.\n"
            f"  HTTP Status : {status}\n"
            f"  Error Code  : {code}\n"
            f"  Message     : {message}\n"
            "\nCheck that:\n"
            "  1. Your NOTION_TOKEN is valid (starts with 'secret_')\n"
            "  2. The parent page exists and the integration is connected to it\n"
            "     (Notion page → ··· menu → Connections → add your integration)\n"
            "  3. NOTION_PARENT_PAGE_ID is the bare UUID, no query string"
        )
        raise RuntimeError(msg) from exc
