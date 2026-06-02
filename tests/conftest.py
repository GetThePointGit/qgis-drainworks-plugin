import sys
from pathlib import Path

import pytest

# Make the plugin package importable when running pytest from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def tmp_gpkg(tmp_path) -> Path:
    return tmp_path / "sewer.gpkg"
