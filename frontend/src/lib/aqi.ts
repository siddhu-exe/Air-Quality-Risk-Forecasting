import type { AQICategory, GRAPStage } from '../types';

export function getAQICategory(aqi: number): AQICategory {
  if (aqi <= 50) return 'Good';
  if (aqi <= 100) return 'Satisfactory';
  if (aqi <= 200) return 'Moderate';
  if (aqi <= 300) return 'Poor';
  if (aqi <= 400) return 'Very Poor';
  return 'Severe';
}

export function getGRAPStage(aqi: number): GRAPStage {
  if (aqi <= 200) return 'NONE';
  if (aqi <= 300) return 'STAGE I';
  if (aqi <= 400) return 'STAGE II';
  if (aqi <= 450) return 'STAGE III';
  return 'STAGE IV';
}

export function getAQIColorClass(category: AQICategory | GRAPStage, type: 'bg' | 'text' | 'border' = 'bg'): string {
  // Mapping to tailwind classes from DESIGN.md
  const map: Record<string, string> = {
    'Good': 'primary',         // Emerarld
    'Satisfactory': 'primary',
    'Moderate': 'secondary',   // Amber
    'Poor': 'secondary',       // Orange / Amber
    'Very Poor': 'secondary-container', // We'll map to robust colors based on the design
    'Severe': 'error',         // Rose / Crimson
    'NONE': 'primary',
    'STAGE I': 'secondary',
    'STAGE II': 'secondary-container',
    'STAGE III': 'error',
    'STAGE IV': 'error-container'
  };

  // Adjustments specifically based on context:
  // "Good / Satisfactory (0–100 AQI): Emerald (#10B981) -> primary-container / primary"
  // "Moderate (101–200 AQI): Amber"
  // "Poor (201–300 AQI): Orange"
  // "Very Poor (301–400 AQI): Rose Crimson" -> wait, error is #ffb4ab. Let's stick to the generated tokens.

  // Actually, let's use exact class prefixes:
  if (category === 'Good' || category === 'Satisfactory') return `${type}-primary`;
  if (category === 'Moderate' || category === 'Poor') return `${type}-secondary`;
  if (category === 'Very Poor') return `${type}-tertiary`; // fallback
  if (category === 'Severe' || category === 'STAGE III' || category === 'STAGE IV') return `${type}-error`;
  if (category === 'STAGE I' || category === 'STAGE II') return `${type}-secondary`;

  return `${type}-surface-variant`;
}
