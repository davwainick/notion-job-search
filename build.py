"""
build.py — Build a single-file executable using PyInstaller.

Run this script from the project root:

    python build.py

The output executable will be placed in the ``dist/`` directory.
Do NOT commit the output to git — it is listed in ``.gitignore``.

Platform detection
------------------
* Windows  → produces ``dist/NotionJobSearch.exe``
* macOS    → produces ``dist/NotionJobSearch``
* Linux    → produces ``dist/NotionJobSearch``

Entry point
-----------
PyInstaller uses ``launcher.py`` (project root) rather than
``notion_job_search/gui.py`` directly.  When PyInstaller freezes a script it
runs it as a top-level module with no parent package, which breaks all
relative imports (``from .state import ...`` etc.).  ``launcher.py`` uses an
absolute import (``from notion_job_search.gui import main``) so the full
package hierarchy is preserved inside the executable.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    """
    Invoke PyInstaller with the correct options for the current platform.

    Raises:
        SystemExit: If PyInstaller returns a non-zero exit code.
    """
    project_root = Path(__file__).parent.resolve()

    # launcher.py at the project root is the correct entry point — see module
    # docstring above for why gui.py cannot be used directly.
    entry_point = project_root / "launcher.py"

    if not entry_point.exists():
        print(f"ERROR: Entry point not found: {entry_point}", file=sys.stderr)
        sys.exit(1)

    is_windows = sys.platform.startswith("win")
    is_mac = sys.platform == "darwin"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "NotionJobSearch",
        "--distpath", str(project_root / "dist"),
        "--workpath", str(project_root / "build"),
        "--specpath", str(project_root),
        # Ensure the entire notion_job_search package is bundled
        "--collect-all", "notion_job_search",
        # Hidden imports the auto-analyser sometimes misses
        "--hidden-import", "notion_client",
        "--hidden-import", "notion_client.client",
        "--hidden-import", "notion_client.errors",
        "--hidden-import", "dotenv",
        "--hidden-import", "cryptography",
        "--hidden-import", "cryptography.fernet",
        "--hidden-import", "cryptography.hazmat.primitives.kdf.pbkdf2",
        "--hidden-import", "cryptography.hazmat.backends",
        # Collect entire third-party packages so data files are included
        "--collect-all", "notion_client",
        "--collect-all", "httpx",
        "--collect-all", "httpcore",
    ]

    if is_windows:
        cmd += ["--noconsole"]
    elif is_mac:
        cmd += ["--noconsole"]
    # Linux: leave console visible so errors are readable during testing

    cmd.append(str(entry_point))

    print("=" * 60)
    print(f"Building NotionJobSearch for {sys.platform} …")
    print(f"Entry point: {entry_point}")
    print("=" * 60)
    print(" ".join(cmd))
    print()

    result = subprocess.run(cmd, cwd=str(project_root))

    if result.returncode != 0:
        print("\nERROR: PyInstaller exited with code", result.returncode, file=sys.stderr)
        sys.exit(result.returncode)

    output = (
        project_root / "dist" / "NotionJobSearch.exe"
        if is_windows
        else project_root / "dist" / "NotionJobSearch"
    )

    print()
    print("=" * 60)
    print("✅ Build complete!")
    print(f"   Executable: {output}")
    print()
    print("Test it with:")
    if is_windows:
        print(f"   {output}")
    else:
        print(f"   chmod +x {output} && {output}")
    print()
    print("⚠️  Do NOT commit dist/ or build/ to git.")
    print("=" * 60)


if __name__ == "__main__":
    main()