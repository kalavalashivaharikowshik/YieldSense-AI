from pydantic import BaseModel


class AnalyticsSummary(BaseModel):
    total_predictions: int
    active_farms: int
    average_predicted_yield: float
    average_estimated_production: float


class CropAnalyticsItem(BaseModel):
    crop: str
    yield_unit: str = "metric tons per hectare"
    prediction_count: int
    average_yield: float


class SeasonAnalyticsItem(BaseModel):
    season: str
    prediction_count: int
    average_yield: float


class StateAnalyticsItem(BaseModel):
    state: str
    prediction_count: int
    average_yield: float


class RecentPredictionItem(BaseModel):
    id: int
    farm_name: str
    crop: str
    season: str
    crop_year: int
    predicted_yield: float
    estimated_production: float
    yield_unit: str = "metric tons per hectare"
    production_unit: str = "metric tons"


class AnalyticsDashboardResponse(BaseModel):
    summary: AnalyticsSummary
    crops: list[CropAnalyticsItem]
    seasons: list[SeasonAnalyticsItem]
    states: list[StateAnalyticsItem]
    recent_predictions: list[RecentPredictionItem]