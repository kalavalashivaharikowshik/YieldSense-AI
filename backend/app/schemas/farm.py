from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

REQUIRED_TEXT_FIELDS = ("farm_name", "state", "district")
OPTIONAL_TEXT_FIELDS = (
    "village",
    "soil_type",
    "primary_crop",
    "irrigation_type",
)


def _collapse_whitespace(value: object) -> object:
    if isinstance(value, str):
        return " ".join(value.split())

    return value


def _empty_to_none(value: object) -> object:
    value = _collapse_whitespace(value)

    if value == "":
        return None

    return value


class FarmBase(BaseModel):
    farm_name: str = Field(
        min_length=2,
        max_length=120,
    )

    state: str = Field(
        min_length=2,
        max_length=120,
    )

    district: str = Field(
        min_length=2,
        max_length=120,
    )

    village: str | None = Field(
        default=None,
        max_length=120,
    )

    area_hectares: float = Field(gt=0)

    soil_type: str | None = Field(
        default=None,
        max_length=100,
    )

    primary_crop: str | None = Field(
        default=None,
        max_length=100,
    )

    irrigation_type: str | None = Field(
        default=None,
        max_length=100,
    )

    latitude: float | None = Field(
        default=None,
        ge=-90,
        le=90,
    )

    longitude: float | None = Field(
        default=None,
        ge=-180,
        le=180,
    )

    # Whitespace is collapsed before length checks run, so a name made
    # only of spaces is rejected instead of being saved as an empty string.
    @field_validator(*REQUIRED_TEXT_FIELDS, mode="before")
    @classmethod
    def normalize_required_text(cls, value: object) -> object:
        return _collapse_whitespace(value)

    @field_validator(*OPTIONAL_TEXT_FIELDS, mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        return _empty_to_none(value)


class FarmCreateRequest(FarmBase):
    pass


class FarmUpdateRequest(BaseModel):
    farm_name: str | None = Field(
        default=None,
        min_length=2,
        max_length=120,
    )

    state: str | None = Field(
        default=None,
        min_length=2,
        max_length=120,
    )

    district: str | None = Field(
        default=None,
        min_length=2,
        max_length=120,
    )

    village: str | None = Field(
        default=None,
        max_length=120,
    )

    area_hectares: float | None = Field(
        default=None,
        gt=0,
    )

    soil_type: str | None = Field(
        default=None,
        max_length=100,
    )

    primary_crop: str | None = Field(
        default=None,
        max_length=100,
    )

    irrigation_type: str | None = Field(
        default=None,
        max_length=100,
    )

    latitude: float | None = Field(
        default=None,
        ge=-90,
        le=90,
    )

    longitude: float | None = Field(
        default=None,
        ge=-180,
        le=180,
    )

    @field_validator(*REQUIRED_TEXT_FIELDS, mode="before")
    @classmethod
    def normalize_required_text(cls, value: object) -> object:
        if value is None:
            raise ValueError("This field cannot be empty")

        return _collapse_whitespace(value)

    @field_validator("area_hectares", mode="before")
    @classmethod
    def reject_null_area(cls, value: object) -> object:
        if value is None:
            raise ValueError("Farm area is required")

        return value

    @field_validator(*OPTIONAL_TEXT_FIELDS, mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        return _empty_to_none(value)


class FarmResponse(BaseModel):
    """Output schema. It carries no input constraints, so a legacy row with
    unusual data can never make the farm list fail to serialize."""

    model_config = ConfigDict(from_attributes=True)

    farm_name: str
    state: str
    district: str
    village: str | None = None
    area_hectares: float
    soil_type: str | None = None
    primary_crop: str | None = None
    irrigation_type: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    id: int
    owner_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class FarmWithOwnerResponse(FarmResponse):
    owner_name: str
    owner_email: str


class FarmSummaryResponse(BaseModel):
    total_farms: int
    active_farms: int
    inactive_farms: int
    total_area_hectares: float
    total_states: int
    total_districts: int