from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

API_ROOT = Path(__file__).resolve().parents[1]


def _alembic_config(url: str) -> Config:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.mark.db
def test_upgrade_and_downgrade_round_trip(test_database_url: str) -> None:
    config = _alembic_config(test_database_url)
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    engine = create_engine(test_database_url)
    try:
        tables = set(inspect(engine).get_table_names())
        assert {"alembic_version", "aircraft", "engines", "flights", "engine_predictions"} <= tables
        command.downgrade(config, "base")
        with engine.connect() as connection:
            versions = connection.exec_driver_sql("SELECT version_num FROM alembic_version").all()
        assert versions == []
    finally:
        command.upgrade(config, "head")  # leave the schema in place for other tests
        engine.dispose()
