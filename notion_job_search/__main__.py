"""
__main__.py — Allows the package to be invoked as ``python -m notion_job_search``.
"""

import sys

from .cli import main

sys.exit(main())
