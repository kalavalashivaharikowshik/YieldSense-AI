"""Run Alembic migrations from inside the application."""

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.db.database import engine

logger = logging.getLogger("yieldsense.migrations")

BACKEND_DIR = Path(__file__).resolve().parents[2]
ALEMBIC_INI_PATH = BACKEND_DIR / "alembic.ini"

# Arbitrary constant so that several workers starting at the same time
# take turns instead of running the same migration concurrently.
MIGRATION_LOCK_ID = 727_165_001


def build_alembic_config() -> Config:
    config = Config(str(ALEMBIC_INI_PATH))
    config.set_main_option(
        "script_location",
        str(BACKEND_DIR / "alembic"),
    )
    config.attributes["configure_logger"] = False

    return config


def run_migrations() -> None:
    config = build_alembic_config()

    with engine.connect() as connection:
        is_postgres = connection.dialect.name == "postgresql"

        if is_postgres:
            connection.execute(
                text("SELECT pg_advisory_lock(:lock_id)"),
                {"lock_id": MIGRATION_LOCK_ID},
            )
            connection.commit()

        try:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            connection.commit()
        finally:
            if is_postgres:
                connection.execute(
                    text("SELECT pg_advisory_unlock(:lock_id)"),
                    {"lock_id": MIGRATION_LOCK_ID},
                )
                connection.commit()

    logger.info("database_migrations_applied")
