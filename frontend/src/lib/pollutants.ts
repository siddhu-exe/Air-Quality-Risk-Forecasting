export const POLLUTANT_KEYS = ['pm25', 'pm10', 'no2', 'co', 'o3', 'so2'] as const
export type PollutantKey = (typeof POLLUTANT_KEYS)[number]

export interface PollutantInfo {
  label: string
  /** Short plain-language qualifier shown beside the name. */
  tag: string
}

export const POLLUTANTS: Record<PollutantKey, PollutantInfo> = {
  pm25: { label: 'PM2.5', tag: 'fine particles' },
  pm10: { label: 'PM10', tag: 'coarse particles' },
  no2: { label: 'NO₂', tag: 'traffic' },
  co: { label: 'CO', tag: '8h mean' },
  o3: { label: 'O₃', tag: '8h mean' },
  so2: { label: 'SO₂', tag: '' },
}
