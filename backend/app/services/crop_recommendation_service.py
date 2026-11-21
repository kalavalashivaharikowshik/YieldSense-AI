from __future__ import annotations

import bisect
import json
import math
import statistics
from typing import Any

import numpy as np
import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.agriculture import (
    HistoricalCropYield,
)
from app.models.crop_recommendation import (
    CropRecommendation,
)
from app.models.user import User
from app.schemas.crop_recommendation import (
    CropRecommendationRequest,
)
from app.services.crop_units import get_crop_unit
from app.services.model_scale import resolve_model_scale
from app.services.prediction_service import (
    build_model_dataframe,
    ensure_finite_number,
    get_active_accessible_farm,
    resolve_soil_reference,
    resolve_weather_reference,
)
from app.services.prediction_validation import (
    resolve_supported_season,
    resolve_supported_state,
)
from ml.model_loader import get_yield_model

MAX_CANDIDATE_CROPS = 30
MAX_ALTERNATIVES = 4
# Crops need at least this many seasons of records to be compared.
MIN_HISTORY_RECORDS = 3
# Number of seasons of records that counts as fully established.
FULL_EXPERIENCE_RECORDS = 15


def normalize_text(value: str) -> str:
    return " ".join(value.strip().split())


def get_candidate_crop_statistics(
    db: Session,
    state_name: str,
    season_name: str,
) -> list[dict[str, Any]]:
    """
    Find crops historically grown in the selected state and season,
    with each crop's own yield history there.

    Fertilizer and pesticide rates and the model's reference area come
    from model_scale, so every crop is evaluated on the scale the model
    was trained on.
    """

    rows = (
        db.query(
            HistoricalCropYield.crop,
            HistoricalCropYield.yield_value,
            HistoricalCropYield.annual_rainfall,
        )
        .filter(
            func.lower(HistoricalCropYield.state)
            == state_name.lower(),
            func.lower(HistoricalCropYield.season)
            == season_name.lower(),
            HistoricalCropYield.crop.isnot(None),
            HistoricalCropYield.yield_value.isnot(None),
        )
        .all()
    )

    history: dict[str, dict[str, list[float]]] = {}

    for crop, yield_value, annual_rainfall in rows:
        crop_name = normalize_text(crop)
        entry = history.setdefault(
            crop_name,
            {"yields": [], "rainfall": []},
        )

        if yield_value is not None and math.isfinite(yield_value):
            entry["yields"].append(float(yield_value))

        if annual_rainfall is not None and math.isfinite(annual_rainfall):
            entry["rainfall"].append(float(annual_rainfall))

    candidates: list[dict[str, Any]] = []

    for crop_name, entry in history.items():
        yields = [value for value in entry["yields"] if value >= 0]

        # A crop needs a few years of history, and a non-zero typical
        # yield, before it can be compared fairly.
        if len(yields) < MIN_HISTORY_RECORDS or not entry["rainfall"]:
            continue

        if statistics.median(yields) <= 0:
            continue

        candidates.append(
            {
                "crop": crop_name,
                "historical_yields": sorted(yields),
                "historical_average_yield": statistics.fmean(yields),
                "annual_rainfall": statistics.fmean(entry["rainfall"]),
                "historical_record_count": len(yields),
            }
        )

    candidates.sort(
        key=lambda item: item["historical_record_count"],
        reverse=True,
    )
    candidates = candidates[:MAX_CANDIDATE_CROPS]

    if not candidates:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "There are not enough historical records to "
                f"recommend a crop for {state_name} during the "
                f"{season_name} season (each crop needs at least "
                f"{MIN_HISTORY_RECORDS} recorded seasons)."
            ),
        )

    return candidates


def resolve_recommendation_environment(
    db: Session,
    request: CropRecommendationRequest,
    current_user: User,
) -> dict[str, Any]:
    farm = get_active_accessible_farm(
        db=db,
        farm_id=request.farm_id,
        current_user=current_user,
    )

    state_name = resolve_supported_state(
        farm.state
    )

    season_name = resolve_supported_season(
        request.season
    )

    soil = resolve_soil_reference(
        db=db,
        state_name=state_name,
    )

    weather = resolve_weather_reference(
        db=db,
        state_name=state_name,
        crop_year=request.crop_year,
    )

    if weather is None:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Weather reference information is not "
                f"available for the state '{state_name}'."
            ),
        )

    values = {
        "farm": farm,
        "farm_id": farm.id,
        "farm_name": farm.farm_name,
        "state": state_name,
        "season": season_name,
        "crop_year": request.crop_year,
        "area_hectares": ensure_finite_number(
            farm.area_hectares,
            "Farm area",
        ),
        "nitrogen": ensure_finite_number(
            soil.nitrogen,
            "Nitrogen",
        ),
        "phosphorus": ensure_finite_number(
            soil.phosphorus,
            "Phosphorus",
        ),
        "potassium": ensure_finite_number(
            soil.potassium,
            "Potassium",
        ),
        "ph": ensure_finite_number(
            soil.ph,
            "Soil pH",
        ),
        "average_temperature_c": (
            ensure_finite_number(
                weather.avg_temp_c,
                "Average temperature",
            )
        ),
        "total_rainfall_mm": (
            ensure_finite_number(
                weather.total_rainfall_mm,
                "Total rainfall",
            )
        ),
        "average_humidity_percent": (
            ensure_finite_number(
                weather.avg_humidity_percent,
                "Average humidity",
            )
        ),
        "weather_reference_year": weather.year,
    }

    return values


def run_candidate_predictions(
    environment: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    model_rows = []
    evaluated = []

    for candidate in candidates:
        model_scale = resolve_model_scale(
            state=environment["state"],
            crop=candidate["crop"],
            season=environment["season"],
        )

        model_values = {
            "crop_year": environment["crop_year"],
            "annual_rainfall": candidate["annual_rainfall"],
            "fertilizer": model_scale.typical_fertilizer_per_hectare,
            "pesticide": model_scale.typical_pesticide_per_hectare,
            "model_scale": model_scale,
            "nitrogen": environment["nitrogen"],
            "phosphorus": environment["phosphorus"],
            "potassium": environment["potassium"],
            "ph": environment["ph"],
            "average_temperature_c": environment[
                "average_temperature_c"
            ],
            "total_rainfall_mm": environment["total_rainfall_mm"],
            "average_humidity_percent": environment[
                "average_humidity_percent"
            ],
            "crop": candidate["crop"],
            "season": environment["season"],
            "state": environment["state"],
        }

        try:
            model_rows.append(build_model_dataframe(model_values))
        except HTTPException:
            # Skip a historical crop the production model cannot use.
            continue

        evaluated.append(candidate)

    if not evaluated:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "No candidate crops could be evaluated "
                "by the current yield model."
            ),
        )

    # One batched model call instead of one call per crop.
    predicted_yields = run_batch_yield_inference(
        pd.concat(model_rows, ignore_index=True)
    )

    results: list[dict[str, Any]] = []

    for candidate, predicted_yield in zip(
        evaluated,
        predicted_yields,
        strict=True,
    ):
        crop_unit = get_crop_unit(candidate["crop"])

        results.append(
            {
                **candidate,
                "predicted_yield": predicted_yield,
                "estimated_production": (
                    predicted_yield * environment["area_hectares"]
                ),
                "yield_unit": crop_unit.yield_unit,
                "production_unit": crop_unit.production_unit,
            }
        )

    return results


def run_batch_yield_inference(
    model_dataframe: pd.DataFrame,
) -> list[float]:
    model_bundle = get_yield_model()

    try:
        log_predictions = model_bundle.pipeline.predict(model_dataframe)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "The yield-prediction model could not "
                "process the supplied inputs"
            ),
        ) from exc

    predictions = []

    for value in np.expm1(np.asarray(log_predictions, dtype=float)):
        predictions.append(
            max(float(value), 0.0) if math.isfinite(value) else 0.0
        )

    return predictions


def percentile_within(values: list[float], value: float) -> float:
    """Share of historical values at or below ``value``, from 0 to 100."""
    if not values:
        return 0.0

    at_or_below = bisect.bisect_right(values, value)

    return 100.0 * at_or_below / len(values)


def rank_candidate_crops(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Rank crops with scores that do not depend on yield units.

    Raw yields of different crops cannot be compared: coconut is
    counted in nuts per hectare (~8,000), sugarcane is ~50 t/ha and
    pulses ~1 t/ha, so ranking by raw yield always picked the heaviest
    crop. Each crop is instead compared with its own history in the same
    state and season:

    * 60% expected performance: where the predicted yield falls among
      the crop's historical yields there (percentile).
    * 25% reliability: how steady the crop's yield has been
      (1 - coefficient of variation).
    * 15% local experience: how many seasons of records exist.
    """

    ranked_candidates = []

    for candidate in candidates:
        yields = candidate["historical_yields"]
        mean_yield = statistics.fmean(yields)
        spread = statistics.pstdev(yields) if len(yields) > 1 else 0.0
        variation = spread / mean_yield if mean_yield > 0 else 1.0

        performance_score = percentile_within(
            yields,
            candidate["predicted_yield"],
        )
        reliability_score = max(0.0, 1.0 - variation) * 100.0
        experience_score = (
            min(
                candidate["historical_record_count"],
                FULL_EXPERIENCE_RECORDS,
            )
            / FULL_EXPERIENCE_RECORDS
            * 100.0
        )

        recommendation_score = (
            performance_score * 0.60
            + reliability_score * 0.25
            + experience_score * 0.15
        )

        ranked_candidates.append(
            {
                **candidate,
                "historical_percentile": round(performance_score, 1),
                "reliability_score": round(reliability_score, 1),
                "recommendation_score": round(
                    recommendation_score,
                    2,
                ),
            }
        )

    ranked_candidates.sort(
        key=lambda item: (
            item["recommendation_score"],
            item["historical_percentile"],
            item["historical_record_count"],
        ),
        reverse=True,
    )

    for rank, candidate in enumerate(
        ranked_candidates,
        start=1,
    ):
        candidate["rank"] = rank

    return ranked_candidates


def determine_recommendation_strength(
    ranked_candidates: list[dict[str, Any]],
) -> str:
    best_score = ranked_candidates[0][
        "recommendation_score"
    ]

    second_score = (
        ranked_candidates[1][
            "recommendation_score"
        ]
        if len(ranked_candidates) > 1
        else 0.0
    )

    score_margin = best_score - second_score

    if best_score >= 75 and score_margin >= 8:
        return "high"

    if best_score >= 55 and score_margin >= 3:
        return "medium"

    return "low"


def create_recommendation_reasons(
    best_crop: dict[str, Any],
    environment: dict[str, Any],
    strength: str,
) -> list[str]:
    reasons = [
        (
            f"{best_crop['crop']} achieved the highest combined "
            "recommendation score among the eligible crops."
        ),
        (
            "Its predicted yield is higher than "
            f"{best_crop['historical_percentile']:.0f}% of its own "
            f"recorded seasons in {environment['state']} during "
            f"{environment['season']}."
        ),
        (
            "Its yield has been "
            + (
                "very steady"
                if best_crop["reliability_score"] >= 75
                else "fairly steady"
                if best_crop["reliability_score"] >= 50
                else "variable"
            )
            + " from year to year (reliability score "
            f"{best_crop['reliability_score']:.0f}/100)."
        ),
        (
            f"It is supported by {best_crop['historical_record_count']} "
            "seasons of historical records for this state and season."
        ),
        (
            f"Weather information from "
            f"{environment['weather_reference_year']} "
            "was used for the evaluation."
        ),
    ]

    if strength == "low":
        reasons.append(
            "The leading crops have similar scores, "
            "so the recommendation should be reviewed "
            "with local agricultural guidance."
        )

    return reasons


def create_recommendation_explanation(
    environment: dict[str, Any],
    candidate_count: int,
) -> str:
    return (
        f"{candidate_count} historically supported "
        "crops were evaluated for "
        f"{environment['state']} during the "
        f"{environment['season']} season with the same state soil "
        "nutrients and weather conditions, and each crop's typical "
        "rainfall, fertilizer and pesticide rates. Because crops are "
        "measured in different units (for example coconuts in nuts), "
        "each crop is compared with its own history rather than with "
        "other crops: 60% where its predicted yield falls among its "
        "past yields in this state and season, 25% how steady its "
        "yield has been, and 15% how many seasons of records exist. "
        "Soil values are state averages, so they are the same for every "
        "farm in the state. This recommendation should support, not "
        "replace, professional agricultural advice."
    )


def serialize_ranked_crop(
    crop: dict[str, Any],
) -> dict[str, Any]:
    return {
        "crop": crop["crop"],
        "rank": crop["rank"],
        "recommendation_score": round(
            crop["recommendation_score"],
            2,
        ),
        "predicted_yield": round(
            crop["predicted_yield"],
            6,
        ),
        "estimated_production": round(
            crop["estimated_production"],
            6,
        ),
        "historical_average_yield": round(
            crop["historical_average_yield"],
            6,
        ),
        "historical_record_count": crop[
            "historical_record_count"
        ],
        "yield_unit": crop["yield_unit"],
        "production_unit": crop["production_unit"],
        "historical_percentile": crop["historical_percentile"],
    }


def create_crop_recommendation(
    db: Session,
    request: CropRecommendationRequest,
    current_user: User,
) -> CropRecommendation:
    environment = (
        resolve_recommendation_environment(
            db=db,
            request=request,
            current_user=current_user,
        )
    )

    candidates = get_candidate_crop_statistics(
        db=db,
        state_name=environment["state"],
        season_name=environment["season"],
    )

    evaluated_candidates = (
        run_candidate_predictions(
            environment=environment,
            candidates=candidates,
        )
    )

    ranked_candidates = rank_candidate_crops(
        evaluated_candidates
    )

    best_crop = ranked_candidates[0]

    strength = (
        determine_recommendation_strength(
            ranked_candidates
        )
    )

    reasons = create_recommendation_reasons(
        best_crop=best_crop,
        environment=environment,
        strength=strength,
    )

    alternatives = [
        serialize_ranked_crop(candidate)
        for candidate in ranked_candidates[
            1 : MAX_ALTERNATIVES + 1
        ]
    ]

    model_bundle = get_yield_model()

    recommendation = CropRecommendation(
        user_id=current_user.id,
        farm_id=environment["farm_id"],
        farm_name=environment["farm_name"],
        state=environment["state"],
        area_hectares=environment[
            "area_hectares"
        ],
        crop_year=environment["crop_year"],
        season=environment["season"],
        nitrogen=environment["nitrogen"],
        phosphorus=environment["phosphorus"],
        potassium=environment["potassium"],
        ph=environment["ph"],
        average_temperature_c=environment[
            "average_temperature_c"
        ],
        total_rainfall_mm=environment[
            "total_rainfall_mm"
        ],
        average_humidity_percent=environment[
            "average_humidity_percent"
        ],
        recommended_crop=best_crop["crop"],
        recommendation_score=best_crop[
            "recommendation_score"
        ],
        recommendation_strength=strength,
        predicted_yield=round(
            best_crop["predicted_yield"],
            6,
        ),
        estimated_production=round(
            best_crop["estimated_production"],
            6,
        ),
        historical_average_yield=round(
            best_crop[
                "historical_average_yield"
            ],
            6,
        ),
        historical_record_count=best_crop[
            "historical_record_count"
        ],
        alternatives_json=json.dumps(
            alternatives
        ),
        reasons_json=json.dumps(reasons),
        model_name=model_bundle.model_name,
        model_version=model_bundle.model_version,
        prediction_unit=best_crop["yield_unit"],
        production_unit=best_crop["production_unit"],
        explanation=(
            create_recommendation_explanation(
                environment=environment,
                candidate_count=len(
                    ranked_candidates
                ),
            )
        ),
    )

    try:
        db.add(recommendation)
        db.commit()
        db.refresh(recommendation)
    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "The crop recommendation was generated "
                "but could not be saved."
            ),
        ) from exc

    return recommendation


def is_admin_user(
    current_user: User,
) -> bool:
    return bool(
        current_user.role
        and current_user.role.name.lower()
        == "admin"
    )


def get_crop_recommendation(
    db: Session,
    recommendation_id: int,
    current_user: User,
) -> CropRecommendation:
    query = db.query(CropRecommendation).filter(
        CropRecommendation.id
        == recommendation_id
    )

    if not is_admin_user(current_user):
        query = query.filter(
            CropRecommendation.user_id
            == current_user.id
        )

    recommendation = query.first()

    if not recommendation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Crop recommendation not found.",
        )

    return recommendation


def get_crop_recommendation_history(
    db: Session,
    current_user: User,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[CropRecommendation], int]:
    query = db.query(CropRecommendation)

    if not is_admin_user(current_user):
        query = query.filter(
            CropRecommendation.user_id
            == current_user.id
        )

    total = query.count()

    recommendations = (
        query.order_by(
            CropRecommendation.created_at.desc()
        )
        .offset(skip)
        .limit(limit)
        .all()
    )

    return recommendations, total


def build_recommendation_response(
    recommendation: CropRecommendation,
) -> dict[str, Any]:
    try:
        alternatives = json.loads(
            recommendation.alternatives_json
            or "[]"
        )

        reasons = json.loads(
            recommendation.reasons_json
            or "[]"
        )
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Stored recommendation details are "
                "invalid."
            ),
        ) from exc

    return {
        "id": recommendation.id,
        "user_id": recommendation.user_id,
        "farm_id": recommendation.farm_id,
        "farm_name": recommendation.farm_name,
        "state": recommendation.state,
        "area_hectares": (
            recommendation.area_hectares
        ),
        "crop_year": recommendation.crop_year,
        "season": recommendation.season,
        "nitrogen": recommendation.nitrogen,
        "phosphorus": (
            recommendation.phosphorus
        ),
        "potassium": recommendation.potassium,
        "ph": recommendation.ph,
        "average_temperature_c": (
            recommendation.average_temperature_c
        ),
        "total_rainfall_mm": (
            recommendation.total_rainfall_mm
        ),
        "average_humidity_percent": (
            recommendation.average_humidity_percent
        ),
        "recommended_crop": (
            recommendation.recommended_crop
        ),
        "recommendation_score": (
            recommendation.recommendation_score
        ),
        "recommendation_strength": (
            recommendation.recommendation_strength
        ),
        "predicted_yield": (
            recommendation.predicted_yield
        ),
        "estimated_production": (
            recommendation.estimated_production
        ),
        "historical_average_yield": (
            recommendation.historical_average_yield
        ),
        "historical_record_count": (
            recommendation.historical_record_count
        ),
        "alternatives": alternatives,
        "reasons": reasons,
        "model_name": recommendation.model_name,
        "model_version": (
            recommendation.model_version
        ),
        "prediction_unit": (
            recommendation.prediction_unit
        ),
        "production_unit": (
            recommendation.production_unit
        ),
        "explanation": recommendation.explanation,
        "created_at": recommendation.created_at,
    }