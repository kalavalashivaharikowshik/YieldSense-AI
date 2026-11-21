// Yields are stored in each crop's own unit. Most crops are in metric
// tons, but coconut is counted in nuts and cotton, jute and mesta in
// bales, so the unit must come from the API instead of being assumed.

const DEFAULT_YIELD_UNIT = "metric tons per hectare";
const DEFAULT_PRODUCTION_UNIT = "metric tons";

export function shortProductionUnit(unit = DEFAULT_PRODUCTION_UNIT) {
  if (!unit || unit === DEFAULT_PRODUCTION_UNIT) {
    return "t";
  }

  // "bales (170 kg each)" -> "bales"
  return unit.replace(/\s*\(.*\)\s*/, "").trim();
}

export function shortYieldUnit(unit = DEFAULT_YIELD_UNIT) {
  const productionUnit = (unit || DEFAULT_YIELD_UNIT).replace(
    / per hectare$/,
    ""
  );

  return `${shortProductionUnit(productionUnit)}/ha`;
}

export function isTonnesUnit(unit) {
  return !unit || unit === DEFAULT_YIELD_UNIT || unit === DEFAULT_PRODUCTION_UNIT;
}
