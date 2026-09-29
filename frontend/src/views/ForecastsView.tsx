import React from 'react';
import { SectionHeader } from '../components/shared/Headers';
import { KPICard } from '../components/shared/KPICard';
import { AQIBadge } from '../components/shared/AQIBadge';

export function ForecastsView() {
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
          <span className="text-primary font-bold font-label-code text-label-code">OPTIMAL CUTOFF τ = 0.38</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-gutter-desktop mt-space-sm">
        <KPICard title="Delhi AQI (Avg)" badge={<AQIBadge category="Very Poor" variant="subtle" />}>
          <div className="flex items-baseline justify-between mt-space-xs">
            <span className="font-metric-display text-metric-display text-secondary tracking-tight font-bold">348</span>
            <span className="font-label-code text-label-code text-error font-bold flex items-center gap-0.5">
              <span className="material-symbols-outlined text-[14px]">trending_up</span>+18 (3h)
            </span>
          </div>
          <div className="mt-space-xs text-on-surface-variant font-label-code text-label-code flex justify-between">
            <span>PM2.5: 198 µg/m³</span>
            <span>PM10: 312 µg/m³</span>
          </div>
        </KPICard>

        <KPICard title="Horizon Forecasts" badge={<span className="font-label-code text-label-code text-primary font-bold">BAYESIAN</span>}>
          <div className="grid grid-cols-3 gap-space-2xs mt-space-xs">
            <div className="p-space-xs rounded bg-surface-container-low text-center">
              <span className="font-label-code text-label-code text-on-surface-variant block">+1h</span>
              <span className="font-headline-sm text-headline-sm font-bold text-secondary block mt-0.5">356</span>
            </div>
            <div className="p-space-xs rounded bg-surface-container-low text-center">
              <span className="font-label-code text-label-code text-on-surface-variant block">+6h</span>
              <span className="font-headline-sm text-headline-sm font-bold text-secondary block mt-0.5">382</span>
            </div>
            <div className="p-space-xs rounded bg-error/10 border border-error/20 text-center">
              <span className="font-label-code text-label-code text-error font-bold block">+24h</span>
              <span className="font-headline-sm text-headline-sm font-bold text-error block mt-0.5">412</span>
            </div>
          </div>
        </KPICard>

        <KPICard title="GRAP III Risk" badge={<AQIBadge category="STAGE III" label="Action: -8h" variant="solid" />}>
          <div className="flex items-baseline justify-between mt-space-xs">
            <span className="font-metric-display text-metric-display text-error font-bold">84.2%</span>
            <span className="font-label-code text-label-code text-tertiary">P(AQI &gt; 400)</span>
          </div>
          <div className="w-full bg-surface-container-highest h-1.5 rounded overflow-hidden mt-space-xs">
            <div className="bg-error h-full" style={{ width: '84.2%' }}></div>
          </div>
        </KPICard>

        <KPICard title="Active Monitoring" badge={<span className="font-label-code text-label-code text-secondary font-bold">1 Calibrating</span>}>
          <div className="flex items-baseline justify-between mt-space-xs">
            <span className="font-metric-display text-metric-display text-on-surface font-bold">7<span className="text-on-surface-variant font-headline-sm font-normal">/7</span></span>
            <span className="font-label-code text-label-code text-primary font-bold">STATIONS LIVE</span>
          </div>
          <div className="grid grid-cols-7 gap-1 mt-space-xs">
            {[...Array(6)].map((_, i) => <div key={i} className="h-1.5 rounded bg-primary"></div>)}
            <div className="h-1.5 rounded bg-secondary animate-pulse"></div>
          </div>
        </KPICard>
      </div>

      <div className="mt-space-md rounded bg-surface-container p-space-md lg:p-space-lg shadow-sm border border-surface-container-high/60">
        <div className="flex flex-wrap items-center justify-between gap-space-md pb-space-sm border-b border-surface-container-high/40">
          <div className="flex items-center gap-space-md">
            <h2 className="font-headline-sm text-headline-sm text-on-surface font-bold tracking-tight">Probabilistic AQI Trajectory</h2>
            <span className="px-space-xs py-0.5 rounded bg-surface-container-high text-primary font-label-code text-label-code font-semibold">MCMC Uncertainty</span>
          </div>
        </div>
        <div className="h-[400px] w-full mt-space-md flex flex-col items-center justify-center border border-surface-container-high/40 rounded bg-surface-container-lowest/50 text-on-surface-variant font-label-code">
          <span className="material-symbols-outlined text-[48px] text-surface-container-highest mb-2">bar_chart</span>
          Interactive Chart Placeholder (Recharts)
        </div>
      </div>
    </>
  );
}
