from __future__ import annotations

import sys
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TEST_TMP_ROOT = ROOT / "outputs" / "_test_tmp"


@pytest.fixture


def local_tmp_path(request: pytest.FixtureRequest):
    """
    Workspace-local temporary directory fixture.
    Avoids OS temp/OneDrive permission issues with pytest tmp_path.
    """
    base = TEST_TMP_ROOT / request.node.name
    if base.exists():
        shutil.rmtree(base, ignore_errors=True)
    base.mkdir(parents=True, exist_ok=True)
    try:
        yield base
    finally:
        shutil.rmtree(base, ignore_errors=True)
