from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class CropRecommendationRequest(BaseModel):
    farm_id: int = Field(
        ...,
        gt=0,
    )

    crop_year: int = Field(
        ...,
        ge=1990,
        le=2100,
    )

    season: str = Field(
        ...,
        min_length=1,
        max_length=50,
    )


class CropRecommendationOption(BaseModel):
    crop: str

    rank: int

    recommendation_score: float

    predicted_yield: float

    estimated_production: float

    historical_average_yield: float

    historical_record_count: int

    # Units differ between crops (e.g. coconut is counted in nuts), so
    # each option carries its own. Older saved options default to tonnes.
    yield_unit: str = "metric tons per hectare"

    production_unit: str = "metric tons"

    # Where the predicted yield falls among this crop's own historical
    # yields in the state and season (0-100).
    historical_percentile: float | None = None


class CropRecommendationResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: int

    user_id: int

    farm_id: int

    farm_name: str

    state: str

    area_hectares: float

    crop_year: int

    season: str

    nitrogen: float

    phosphorus: float

    potassium: float

    ph: float

    average_temperature_c: float

    total_rainfall_mm: float

    average_humidity_percent: float

    recommended_crop: str

    recommendation_score: float

    recommendation_strength: str

    predicted_yield: float

    estimated_production: float

    historical_average_yield: float

    historical_record_count: int

    alternatives: list[
        CropRecommendationOption
    ]

    reasons: list[str]

    model_name: str

    model_version: str

    prediction_unit: str

    production_unit: str

    explanation: str | None

    created_at: datetime


class CropRecommendationHistoryItem(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: int

    farm_id: int

    farm_name: str

    state: str

    crop_year: int

    season: str

    recommended_crop: str

    recommendation_score: float

    recommendation_strength: str

    predicted_yield: float

    estimated_production: float

    created_at: datetime


class CropRecommendationHistoryResponse(
    BaseModel
):
    items: list[
        CropRecommendationHistoryItem
    ]

    total: int