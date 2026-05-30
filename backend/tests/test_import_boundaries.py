"""Verify the import-linter contracts pass.

Acts as a CI tripwire if devs forget to run lint-imports.
"""

import subprocess
from pathlib import Path


def test_import_linter_contracts_hold() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["uv", "run", "lint-imports", "--config", ".importlinter"],
        cwd=backend_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"import-linter contracts broken:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
