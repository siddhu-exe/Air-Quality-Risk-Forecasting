export const COST_OPTIMAL_THRESHOLD = 341.5;

export function isCostOptimalAlert(predictedAQI: number): boolean {
  return predictedAQI >= COST_OPTIMAL_THRESHOLD;
}
