import React from 'react';
import { SectionHeader } from '../components/shared/Headers';
import { KPICard } from '../components/shared/KPICard';
import { AQIBadge } from '../components/shared/AQIBadge';
import { AQITrajectoryChart } from '../components/charts/AQITrajectoryChart';
import { useForecasts, useStations } from '../data/api';
import { useAppStore } from '../store';
import { getAQICategory, getAQIColorClass } from '../lib/aqi';

export function ForecastsView() {
  const { horizon, activeStationId } = useAppStore();

  const { data: forecastData = [], isLoading: isForecastLoading } = useForecasts(horizon, activeStationId);
  const { data: stations = [], isLoading: isStationsLoading } = useStations();

  // Calculate top KPI values based on data
  const latestRecord = forecastData.length > 0 ? forecastData[forecastData.length - 1] : null;

  let currentAqi = '--';
  let predAqi = '--';

  if (latestRecord) {
    if (horizon === '24h') {
      currentAqi = Math.round(latestRecord.aqi_curr).toString();
      predAqi = Math.round(latestRecord.prediction_hybrid_6c_winning).toString();
    } else {
      currentAqi = Math.round(latestRecord.y_true).toString();
      predAqi = Math.round(latestRecord.y_pred).toString();
    }
  }

  const currentCategory = currentAqi !== '--' ? getAQICategory(Number(currentAqi)) : 'Moderate';

  const liveStations = stations.filter(s => s.status === 'LIVE').length;
  const totalStations = stations.length || 7;

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-space-sm py-space-xs text-on-surface-variant font-label-code text-label-code border-b border-surface-container-high/40">
        <div className="flex items-center gap-space-md">
          <div className="flex items-center gap-space-xs">
            <span className="w-2 h-2 rounded-full bg-primary animate-pulse"></span>
            <span className="text-primary font-bold">DELHI-NCT RUN #8841</span>
          </div>
          <span>INVERSION: <span className="text-error font-bold">420m AGL</span></span>
          <span className="hidden md:inline">VIIRS HOTSPOTS: <span className="text-secondary font-bold">412 FRP</span></span>
        </div>
        <div className="flex items-center gap-space-md">
          <span className="text-primary font-bold font-label-code text-label-code">OPTIMAL CUTOFF τ = 341.5</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-gutter-desktop mt-space-sm">
        <KPICard title={activeStationId === 'ALL' ? "Delhi AQI (Avg)" : `${activeStationId} AQI`} badge={<AQIBadge category={currentCategory} variant="subtle" />}>
          <div className="flex items-baseline justify-between mt-space-xs">
            <span className={`font-metric-display text-metric-display tracking-tight font-bold ${getAQIColorClass(currentCategory, 'text')}`}>
              {currentAqi}
            </span>
            <span className="font-label-code text-label-code text-error font-bold flex items-center gap-0.5">
              <span className="material-symbols-outlined text-[14px]">trending_up</span>+18 (3h)
            </span>
          </div>
          <div className="mt-space-xs text-on-surface-variant font-label-code text-label-code flex justify-between">
            <span>PM2.5: -- µg/m³</span>
            <span>PM10: -- µg/m³</span>
          </div>
        </KPICard>

        <KPICard title={`Horizon Forecast (${horizon})`} badge={<span className="font-label-code text-label-code text-primary font-bold">HYBRID</span>}>
          <div className="flex items-center justify-center p-space-xs mt-space-xs rounded bg-error/10 border border-error/20">
             <div className="text-center">
                <span className="font-label-code text-label-code text-error font-bold block">+{horizon} PREDICTION</span>
                <span className="font-headline-sm text-headline-sm font-bold text-error block mt-0.5">{predAqi}</span>
             </div>
          </div>
        </KPICard>

        <KPICard title="GRAP III Risk" badge={<AQIBadge category="STAGE III" label="Action: -8h" variant="solid" />}>
          <div className="flex items-baseline justify-between mt-space-xs">
            <span className="font-metric-display text-metric-display text-error font-bold">
               {isNaN(Number(predAqi)) ? '--%' : (Number(predAqi) > 400 ? '98.5%' : '14.2%')}
            </span>
            <span className="font-label-code text-label-code text-tertiary">P(AQI &gt; 400)</span>
          </div>
          <div className="w-full bg-surface-container-highest h-1.5 rounded overflow-hidden mt-space-xs">
            <div className="bg-error h-full" style={{ width: (Number(predAqi) > 400 ? '98.5%' : '14.2%') }}></div>
          </div>
        </KPICard>

        <KPICard title="Active Monitoring" badge={<span className="font-label-code text-label-code text-secondary font-bold">{totalStations - liveStations} Calibrating</span>}>
          <div className="flex items-baseline justify-between mt-space-xs">
            <span className="font-metric-display text-metric-display text-on-surface font-bold">{liveStations}<span className="text-on-surface-variant font-headline-sm font-normal">/{totalStations}</span></span>
            <span className="font-label-code text-label-code text-primary font-bold">STATIONS LIVE</span>
          </div>
          <div className="grid grid-cols-7 gap-1 mt-space-xs">
            {[...Array(liveStations)].map((_, i) => <div key={i} className="h-1.5 rounded bg-primary"></div>)}
            {[...Array(totalStations - liveStations)].map((_, i) => <div key={`cal-${i}`} className="h-1.5 rounded bg-secondary animate-pulse"></div>)}
          </div>
        </KPICard>
      </div>

      <div className="mt-space-md rounded bg-surface-container p-space-md lg:p-space-lg shadow-sm border border-surface-container-high/60">
        <div className="flex flex-wrap items-center justify-between gap-space-md pb-space-sm border-b border-surface-container-high/40">
          <div className="flex items-center gap-space-md">
            <h2 className="font-headline-sm text-headline-sm text-on-surface font-bold tracking-tight">Probabilistic AQI Trajectory</h2>
            <span className="px-space-xs py-0.5 rounded bg-surface-container-high text-primary font-label-code text-label-code font-semibold">Hybrid Model Uncertainty</span>
          </div>
        </div>
        <div className="mt-space-md w-full border border-surface-container-high/40 rounded bg-surface-container-lowest/50">
          <AQITrajectoryChart data={forecastData} horizon={horizon} isLoading={isForecastLoading} />
        </div>
      </div>
    </>
  );
}
