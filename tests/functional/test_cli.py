import os
import subprocess
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


@pytest.mark.functional
def test_cli_init_uses_isolated_database(tmp_path):
    database = tmp_path / "functional.db"
    env = os.environ.copy()
    env["JOB_ENGINE_DB_PATH"] = str(database)

    result = subprocess.run(
        [sys.executable, "main.py", "init", "--config", "config.example.yaml"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert database.exists()
    assert "Database initialized" in result.stdout
