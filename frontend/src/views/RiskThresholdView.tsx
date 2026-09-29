import React, { useState } from 'react';
import { SectionHeader } from '../components/shared/Headers';
import { KPICard } from '../components/shared/KPICard';
import { COST_OPTIMAL_THRESHOLD } from '../lib/thresholds';

export function RiskThresholdView() {
  const [threshold, setThreshold] = useState<number>(COST_OPTIMAL_THRESHOLD);

  return (
    <>
      <SectionHeader title="COST-AWARE THRESHOLD OPTIMIZER" subtitle="| ASYMMETRIC LOSS MATRIX" />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-gutter-desktop mt-space-sm">
        <KPICard title="Decision Boundary">
          <div className="mt-space-md flex flex-col gap-4">
            <div className="flex justify-between font-label-code">
              <span className="text-on-surface-variant">Threshold cutoff (AQI)</span>
              <span className="text-primary font-bold">{threshold}</span>
            </div>
            <input
              type="range"
              min="200"
              max="450"
              step="1"
              value={threshold}
              onChange={(e) => setThreshold(Number(e.target.value))}
              className="w-full accent-primary"
            />
            <div className="flex justify-between font-label-code text-[10px] text-on-surface-variant">
              <span>More False Alarms</span>
              <span>More Missed Crises</span>
            </div>
          </div>
        </KPICard>

        <KPICard title="Confusion Matrix Output" badge={<span className="text-on-surface-variant font-label-code">Test Set</span>}>
          <div className="grid grid-cols-2 gap-space-xs mt-space-sm font-label-code text-center">
            <div className="bg-surface-container-high p-4 rounded border border-primary/20">
              <div className="text-[10px] text-on-surface-variant uppercase mb-1">True Positive (Crisis caught)</div>
              <div className="text-xl text-primary font-bold">1,820</div>
            </div>
            <div className="bg-surface-container-high p-4 rounded border border-error/50">
              <div className="text-[10px] text-on-surface-variant uppercase mb-1">False Negative (MISS)</div>
              <div className="text-xl text-error font-bold tracking-wider">173</div>
            </div>
            <div className="bg-surface-container-high p-4 rounded border border-secondary/30">
              <div className="text-[10px] text-on-surface-variant uppercase mb-1">False Positive (Alarm)</div>
              <div className="text-xl text-secondary">3,242</div>
            </div>
            <div className="bg-surface-container-high p-4 rounded border border-surface-container-highest">
              <div className="text-[10px] text-on-surface-variant uppercase mb-1">True Negative (Ok)</div>
              <div className="text-xl text-on-surface">4,550</div>
            </div>
          </div>
        </KPICard>
      </div>

      <div className="mt-space-md rounded bg-surface-container p-space-md lg:p-space-lg shadow-sm border border-surface-container-high/60">
         <h2 className="font-headline-sm text-on-surface font-bold mb-4">Precision-Recall Tradeoff Surface</h2>
         <div className="h-[300px] border border-surface-container-high/40 rounded bg-surface-container-lowest flex items-center justify-center text-on-surface-variant font-label-code">
           Tradeoff Chart Placeholder
         </div>
      </div>
    </>
  );
}
