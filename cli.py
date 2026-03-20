"""
cli.py — Command-line interface for notion-job-search.

Usage
-----
::

    python -m notion_job_search [OPTIONS]

    Options:
      --dry-run     Print what would be created without calling the Notion API.
      --seed-data   Insert five sample company rows after scaffolding.
      --token TEXT  Notion integration token (overrides NOTION_TOKEN env var).
      --parent TEXT Notion parent page ID (overrides NOTION_PARENT_PAGE_ID env var).
      --verbose     Enable DEBUG-level logging.
      --help        Show this message and exit.

The script loads ``.env`` automatically via ``python-dotenv`` so you do not
need to export variables manually before running.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import traceback

from dotenv import load_dotenv  # type: ignore

from .builder import build_workspace
from .client import get_client


def _build_arg_parser() -> argparse.ArgumentParser:
    """
    Construct and return the argument parser for the CLI.

    Returns:
        A configured :class:`argparse.ArgumentParser` instance.
    """
    parser = argparse.ArgumentParser(
        prog="notion-job-search",
        description=(
            "Scaffold a job-search CRM workspace in Notion — "
            "four linked databases modelled on a B2B sales pipeline."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview exactly what would be created, no API calls:
  python -m notion_job_search --dry-run

  # Build the workspace and seed with 5 sample companies:
  python -m notion_job_search --seed-data

  # Build with verbose logging:
  python -m notion_job_search --seed-data --verbose

  # Override credentials inline (useful in CI):
  python -m notion_job_search --token secret_xxx --parent abc123 --seed-data
        """,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help=(
            "Simulate all operations and print the payloads that WOULD be sent "
            "to the Notion API, without making any actual API calls.  Useful "
            "for previewing the workspace structure before committing."
        ),
    )
    parser.add_argument(
        "--seed-data",
        action="store_true",
        default=False,
        help=(
            "After scaffolding the databases, insert five sample healthcare IT "
            "company rows (Epic, Health Catalyst, Greenway Health, Veeva, "
            "ServiceNow) with realistic 'Why You Fit' notes."
        ),
    )
    parser.add_argument(
        "--token",
        metavar="TOKEN",
        default=None,
        help=(
            "Notion integration token.  Overrides the NOTION_TOKEN environment "
            "variable.  If omitted, the value from .env is used."
        ),
    )
    parser.add_argument(
        "--parent",
        metavar="PAGE_ID",
        default=None,
        help=(
            "Notion page ID of the root page that will contain Job Search HQ. "
            "Overrides the NOTION_PARENT_PAGE_ID environment variable."
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable DEBUG-level logging (very chatty — mainly for development).",
    )

    return parser


def _configure_logging(verbose: bool) -> None:
    """
    Configure the root logger for console output.

    Args:
        verbose: If *True*, set level to ``DEBUG``; otherwise ``INFO``.
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        stream=sys.stdout,
    )


def main(argv: list[str] | None = None) -> int:
    """
    Entry point for the ``notion-job-search`` CLI command.

    Loads ``.env``, validates credentials, then delegates to
    :func:`builder.build_workspace`.

    Args:
        argv: Argument list (defaults to ``sys.argv[1:]`` when *None*).

    Returns:
        Exit code — ``0`` on success, ``1`` on error.
    """
    # Load .env before parsing args so env vars are available as defaults.
    load_dotenv()

    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)

    logger = logging.getLogger(__name__)

    # Resolve credentials — CLI flags take precedence over env vars.
    token = args.token or os.getenv("NOTION_TOKEN")
    parent_page_id = args.parent or os.getenv("NOTION_PARENT_PAGE_ID")

    if not token:
        logger.error(
            "❌  No Notion token found.\n"
            "    Set NOTION_TOKEN in your .env file or pass --token on the CLI."
        )
        return 1

    if not parent_page_id and not args.dry_run:
        logger.error(
            "❌  No parent page ID found.\n"
            "    Set NOTION_PARENT_PAGE_ID in your .env file or pass --parent on the CLI.\n"
            "    (Tip: use --dry-run to preview without a real page ID.)"
        )
        return 1

    # Use a placeholder in dry-run mode so the rest of the code can run.
    if args.dry_run and not parent_page_id:
        parent_page_id = "dry-run-parent-page-id"

    try:
        client = get_client(token)
        result = build_workspace(
            client,
            parent_page_id,
            dry_run=args.dry_run,
            seed_data=args.seed_data,
        )
    except RuntimeError as exc:
        logger.error("❌  %s", exc)
        return 1
    except Exception as exc:  # noqa: BLE001
        logger.error("❌  Unexpected error: %s", exc)
        traceback.print_exc()
        return 1

    if not args.dry_run:
        logger.info("\n📋 Created resource IDs:")
        for key, value in result.items():
            logger.info("   %-20s %s", key + ":", value)

    return 0


if __name__ == "__main__":
    sys.exit(main())
