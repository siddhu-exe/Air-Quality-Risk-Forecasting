export type Horizon = '1h' | '6h' | '24h';

export type AQICategory = 'Good' | 'Satisfactory' | 'Moderate' | 'Poor' | 'Very Poor' | 'Severe';

export type GRAPStage = 'STAGE I' | 'STAGE II' | 'STAGE III' | 'STAGE IV' | 'NONE';

export interface Station {
  id: string;
  name: string;
  aqi: number;
  status: 'LIVE' | 'OFFLINE' | 'CALIBRATING';
}

export interface Metric {
  value: number;
  delta?: number;
  label: string;
  unit?: string;
}

export interface ForecastRecord {
  timestamp: string;
  actual_aqi: number;
  predicted_aqi: number;
  lower_bound?: number;
  upper_bound?: number;
}
