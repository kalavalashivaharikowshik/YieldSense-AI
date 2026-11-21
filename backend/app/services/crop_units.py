"""Units of the yield values in the historical crop dataset.

The source statistics (Government of India crop production data) record
production in tonnes for most crops, but count coconuts in nuts and
cotton, jute and mesta in bales. Yield is production divided by area, so
those crops have different yield units. Showing them all as "metric
tons per hectare" turned Kerala's ~6,400 nuts per hectare into 6,400
tonnes per hectare.
"""

from __future__ import annotations

from dataclasses import dataclass

TONNES = "metric tons"


@dataclass(frozen=True)
class CropUnit:
    production_unit: str

    @property
    def yield_unit(self) -> str:
        return f"{self.production_unit} per hectare"

    @property
    def is_tonnes(self) -> bool:
        return self.production_unit == TONNES


_SPECIAL_UNITS = {
    "coconut": CropUnit("nuts"),
    "cotton(lint)": CropUnit("bales (170 kg each)"),
    "jute": CropUnit("bales (180 kg each)"),
    "mesta": CropUnit("bales (180 kg each)"),
}

DEFAULT_UNIT = CropUnit(TONNES)


def get_crop_unit(crop: str) -> CropUnit:
    key = "".join(crop.split()).casefold()

    for special_name, unit in _SPECIAL_UNITS.items():
        if key == "".join(special_name.split()):
            return unit

    return DEFAULT_UNIT


def is_tonnes_crop(crop: str) -> bool:
    return get_crop_unit(crop).is_tonnes
