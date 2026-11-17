from pathlib import Path

import pytest

from aerofleet_ml.data.synthetic import write_synthetic_dataset


@pytest.fixture(scope="session")
def synthetic_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Explicitly synthetic C-MAPSS-format data (see aerofleet_ml.data.synthetic)."""
    return write_synthetic_dataset(tmp_path_factory.mktemp("synthetic"))
