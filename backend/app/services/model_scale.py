"""Translate farm-level inputs into the scale the yield model was trained on.

The training data comes from state-level crop statistics. In it:

* ``Area`` is the total area of one crop in one state and season
  (median about 9,300 hectares), and
* ``Fertilizer`` and ``Pesticide`` are totals for that whole area, so
  ``Fertilizer / Area`` is a rate in kg per hectare (about 95-194).

A single farm is usually only a few hectares. Feeding its own area and
whatever fertilizer number the farmer typed put the model far outside
anything it had seen: a 2-hectare Kerala coconut farm was predicted at
about 12 while the same inputs at state scale gave about 6,480.

The model predicts yield per hectare, which does not depend on how big
the area is. So instead of the farm's own size, the model receives the
typical crop area for the same state, crop and season from the training
data, and fertilizer and pesticide are entered per hectare and scaled to
that area. The farm's real size is only used afterwards, to turn the
predicted yield into estimated production.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import pandas as pd

from app.services.prediction_validation import (
    PROCESSED_DATASET_PATH,
    normalize_lookup_key,
)

FERTILIZER_PER_HECTARE_MAX = 2000.0
PESTICIDE_PER_HECTARE_MAX = 100.0


@dataclass(frozen=True)
class ModelScale:
    reference_area: float
    typical_fertilizer_per_hectare: float
    typical_pesticide_per_hectare: float
    record_count: int
    basis: str

    def model_inputs(
        self,
        fertilizer_per_hectare: float,
        pesticide_per_hectare: float,
    ) -> dict[str, float]:
        return {
            "Area": self.reference_area,
            "Fertilizer": fertilizer_per_hectare * self.reference_area,
            "Pesticide": pesticide_per_hectare * self.reference_area,
        }


def _summaries(dataframe: pd.DataFrame, keys: list[str]) -> dict:
    grouped = dataframe.groupby(keys).agg(
        reference_area=("Area", "median"),
        fertilizer_per_hectare=("fertilizer_per_hectare", "median"),
        pesticide_per_hectare=("pesticide_per_hectare", "median"),
        record_count=("Area", "size"),
    )

    summaries = {}

    for index, row in grouped.iterrows():
        index_values = index if isinstance(index, tuple) else (index,)
        summaries[tuple(normalize_lookup_key(str(v)) for v in index_values)] = (
            row.to_dict()
        )

    return summaries


@lru_cache(maxsize=1)
def _scale_tables() -> dict:
    dataframe = pd.read_csv(
        PROCESSED_DATASET_PATH,
        usecols=["Crop", "Season", "State", "Area", "Fertilizer", "Pesticide"],
    )
    dataframe = dataframe[dataframe["Area"] > 0].copy()
    dataframe["fertilizer_per_hectare"] = (
        dataframe["Fertilizer"] / dataframe["Area"]
    )
    dataframe["pesticide_per_hectare"] = (
        dataframe["Pesticide"] / dataframe["Area"]
    )

    return {
        "state_crop_season": _summaries(dataframe, ["State", "Crop", "Season"]),
        "state_crop": _summaries(dataframe, ["State", "Crop"]),
        "crop": _summaries(dataframe, ["Crop"]),
        "all": {
            "reference_area": float(dataframe["Area"].median()),
            "fertilizer_per_hectare": float(
                dataframe["fertilizer_per_hectare"].median()
            ),
            "pesticide_per_hectare": float(
                dataframe["pesticide_per_hectare"].median()
            ),
            "record_count": int(len(dataframe)),
        },
    }


def resolve_model_scale(state: str, crop: str, season: str) -> ModelScale:
    tables = _scale_tables()
    state_key = normalize_lookup_key(state)
    crop_key = normalize_lookup_key(crop)
    season_key = normalize_lookup_key(season)

    candidates = [
        (
            tables["state_crop_season"].get((state_key, crop_key, season_key)),
            f"{crop} in {state} during {season}",
        ),
        (tables["state_crop"].get((state_key, crop_key)), f"{crop} in {state}"),
        (tables["crop"].get((crop_key,)), f"{crop} across all states"),
        (tables["all"], "all crops"),
    ]

    for summary, basis in candidates:
        if summary:
            return ModelScale(
                reference_area=float(summary["reference_area"]),
                typical_fertilizer_per_hectare=float(
                    summary["fertilizer_per_hectare"]
                ),
                typical_pesticide_per_hectare=float(
                    summary["pesticide_per_hectare"]
                ),
                record_count=int(summary["record_count"]),
                basis=basis,
            )

    raise RuntimeError("Model scale reference data is empty")


def clear_model_scale_cache() -> None:
    _scale_tables.cache_clear()
