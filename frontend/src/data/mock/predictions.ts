import type { ForecastRecord } from '../../types';

export const generateMockPredictions = (horizon: '1h' | '6h' | '24h'): ForecastRecord[] => {
  const baseAQI = horizon === '1h' ? 350 : horizon === '6h' ? 380 : 410;
  const variance = horizon === '24h' ? 50 : 20;

  return Array.from({ length: 24 }).map((_, i) => {
    // Generate some timestamps for today starting at 00:00
    const ts = new Date();
    ts.setHours(i, 0, 0, 0);

    const actual = baseAQI + Math.sin(i / 3) * variance;
    const predicted = actual + (Math.random() - 0.5) * variance * 0.5;

    return {
      timestamp: ts.toISOString(),
      actual_aqi: Math.round(actual),
      predicted_aqi: Math.round(predicted),
      lower_bound: Math.round(predicted - 15),
      upper_bound: Math.round(predicted + 15),
    };
  });
};

export const predictions1h = generateMockPredictions('1h');
export const predictions6h = generateMockPredictions('6h');
export const predictions24h = generateMockPredictions('24h');
