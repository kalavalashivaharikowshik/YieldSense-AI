"""Load the bundled reference datasets into the database.

Usage (from the backend folder):

    python -m scripts.load_reference_data

Imports ml/data/raw/historical_crop_yield.csv, state_soil.csv and
state_weather.csv with the same validation as the admin upload screen.
Safe to run more than once: existing rows are skipped or updated.
"""

from pathlib import Path

from app.db.database import SessionLocal
from app.models import (  # noqa: F401
    agriculture,
    crop_recommendation,
    farm,
    prediction,
    user,
)
from app.services.dataset_import_service import (
    import_historical_crop_yield,
    import_state_soil,
    import_state_weather,
)

RAW_DATA_DIR = Path(__file__).resolve().parents[1] / "ml" / "data" / "raw"

DATASETS = [
    ("state_soil.csv", import_state_soil),
    ("state_weather.csv", import_state_weather),
    ("historical_crop_yield.csv", import_historical_crop_yield),
]


def main() -> None:
    session = SessionLocal()

    try:
        for file_name, importer in DATASETS:
            result = importer(
                db=session,
                file_content=(RAW_DATA_DIR / file_name).read_bytes(),
            )
            print(
                f"{file_name}: inserted={result['inserted_rows']} "
                f"updated={result['updated_rows']} "
                f"skipped={result['skipped_rows']} "
                f"invalid={result['invalid_rows']}"
            )
    finally:
        session.close()


if __name__ == "__main__":
    main()
