import React from 'react';
import { SectionHeader } from '../components/shared/Headers';
import { KPICard } from '../components/shared/KPICard';

export function ModelPerformanceView() {
  return (
    <>
      <SectionHeader title="VALIDATION RUN #842-NCR" subtitle="| OUT-OF-SAMPLE TEST SET (NOV-DEC 2025)" />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-gutter-desktop mt-space-sm">
        <KPICard title="T+1h Tactical" badge={<span className="text-secondary font-label-code">LightGBM</span>}>
          <div className="grid grid-cols-2 gap-y-space-md mt-space-sm">
            <div>
              <div className="font-label-code text-on-surface-variant text-[10px] uppercase">Test MAE</div>
              <div className="font-metric-display text-[24px] text-on-surface">2.29</div>
            </div>
            <div>
              <div className="font-label-code text-on-surface-variant text-[10px] uppercase">Test R²</div>
              <div className="font-metric-display text-[24px] text-primary">0.996</div>
            </div>
          </div>
        </KPICard>

        <KPICard title="T+6h Operational" badge={<span className="text-secondary font-label-code">LightGBM</span>}>
          <div className="grid grid-cols-2 gap-y-space-md mt-space-sm">
            <div>
              <div className="font-label-code text-on-surface-variant text-[10px] uppercase">Test MAE</div>
              <div className="font-metric-display text-[24px] text-on-surface">11.84</div>
            </div>
            <div>
              <div className="font-label-code text-on-surface-variant text-[10px] uppercase">Test R²</div>
              <div className="font-metric-display text-[24px] text-primary">0.913</div>
            </div>
          </div>
        </KPICard>

        <KPICard title="T+24h Strategic" badge={<span className="text-error font-label-code">Hybrid Ridge</span>} className="border-error/30">
          <div className="grid grid-cols-2 gap-y-space-md mt-space-sm">
            <div>
              <div className="font-label-code text-on-surface-variant text-[10px] uppercase">Test MAE</div>
              <div className="font-metric-display text-[24px] text-error font-bold">34.11</div>
            </div>
            <div>
              <div className="font-label-code text-on-surface-variant text-[10px] uppercase">Test R²</div>
              <div className="font-metric-display text-[24px] text-error">0.365</div>
            </div>
          </div>
        </KPICard>
      </div>

      <div className="mt-space-md rounded bg-surface-container p-space-md lg:p-space-lg shadow-sm border border-surface-container-high/60">
        <h2 className="font-headline-sm text-on-surface font-bold">Error Distribution & Feature Importance</h2>
        <div className="h-[300px] w-full mt-space-sm border border-surface-container-high/40 rounded bg-surface-container-lowest flex items-center justify-center text-on-surface-variant font-label-code">
          SHAP / Residuals Chart Placeholder
        </div>
      </div>
    </>
  );
}
