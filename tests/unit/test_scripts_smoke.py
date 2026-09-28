"""Every CLI script must at least compile and parse its arguments."""

from __future__ import annotations

import os
import py_compile
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = sorted((ROOT / "scripts").glob("*.py"))


@pytest.mark.parametrize("path", SCRIPTS, ids=lambda p: p.name)
def test_script_compiles(path: Path) -> None:
    py_compile.compile(str(path), doraise=True)


@pytest.mark.parametrize("name", ["run_pipeline.py", "run_stage.py"])
def test_orchestrators_parse_args(name: str) -> None:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / name), "--help"],
        capture_output=True, text=True, env=env, cwd=str(ROOT),
    )
    assert result.returncode == 0, result.stderr
    assert "--include-pre-v1-floor" in result.stdout
