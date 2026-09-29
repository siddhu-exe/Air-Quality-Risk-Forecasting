import React from 'react';
import { SectionHeader } from '../components/shared/Headers';
import { KPICard } from '../components/shared/KPICard';
import { DiwaliCausalChart } from '../components/charts/DiwaliCausalChart';
import { useDiwaliCausal } from '../data/api';

export function CausalImpactView() {
  const { data: diwaliData = [], isLoading } = useDiwaliCausal();

  return (
    <>
      <SectionHeader title="NODE: CAQM-DEL-SYNTH-84" subtitle="| ECONOMETRIC POLICY EVALUATION (DIWALI 2025)" />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-gutter-desktop mt-space-sm">
        <KPICard title="Net Pyrotechnic Spike" badge={<span className="text-error font-label-code">p &lt; 0.001</span>}>
          <div className="flex items-baseline justify-between mt-space-sm">
            <span className="font-metric-display text-[28px] text-error font-bold">+142<span className="text-on-surface-variant font-headline-sm"> AQI</span></span>
            <span className="material-symbols-outlined text-error">trending_up</span>
          </div>
        </KPICard>

        <KPICard title="Actual Peak (Factual)" badge={<span className="text-secondary font-label-code">Observed</span>}>
          <div className="flex items-baseline justify-between mt-space-sm">
            <span className="font-metric-display text-[28px] text-on-surface font-bold">360</span>
            <span className="font-label-code text-error border border-error/30 px-1 rounded bg-error/10">Very Poor</span>
          </div>
        </KPICard>

        <KPICard title="Counterfactual Peak" badge={<span className="text-primary font-label-code">Synthetic</span>}>
          <div className="flex items-baseline justify-between mt-space-sm">
            <span className="font-metric-display text-[28px] text-primary font-bold">218</span>
            <span className="font-label-code text-secondary border border-secondary/30 px-1 rounded bg-secondary/10">Poor</span>
          </div>
        </KPICard>

        <KPICard title="Atmospheric Dissipation" badge={<span className="text-on-surface font-label-code">T-Half</span>}>
          <div className="flex items-baseline justify-between mt-space-sm">
            <span className="font-metric-display text-[28px] text-on-surface font-bold">18-24<span className="text-on-surface-variant font-headline-sm">h</span></span>
            <span className="material-symbols-outlined text-outline">air</span>
          </div>
        </KPICard>
      </div>

      <div className="mt-space-md rounded bg-surface-container p-space-md lg:p-space-lg shadow-sm border border-surface-container-high/60">
        <h2 className="font-headline-sm text-on-surface font-bold mb-4">Interrupted Time Series & Synthetic Control Analysis</h2>
        <div className="h-[400px] w-full border border-surface-container-high/40 rounded bg-surface-container-lowest text-on-surface-variant font-label-code">
          <DiwaliCausalChart data={diwaliData} isLoading={isLoading} />
        </div>
      </div>
    </>
  );
}
