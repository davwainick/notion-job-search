"""
launcher.py — PyInstaller entry point for the NotionJobSearch executable.

This file lives at the project root (outside the package) so PyInstaller
treats it as a top-level script.  It imports the GUI via an absolute package
import, which means all relative imports inside the package resolve correctly
when running as a frozen executable.

Do not run this file directly during development — use:
    python -m notion_job_search.gui
"""

from notion_job_search.gui import main

if __name__ == "__main__":
    main()