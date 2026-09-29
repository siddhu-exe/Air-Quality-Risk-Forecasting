import React from 'react';
import { SectionHeader } from '../components/shared/Headers';

export function MethodologyView() {
  return (
    <>
      <SectionHeader title="ARCHITECTURE & PROTOCOLS" subtitle="| SYSTEM SPECIFICATIONS" />

      <div className="mt-space-sm bg-surface-container rounded border border-surface-container-high/60 p-space-md lg:p-space-lg prose prose-invert max-w-none prose-p:text-on-surface-variant prose-headings:text-on-surface">
        <h2 className="font-headline-sm font-bold text-on-surface mb-2">System Architecture</h2>
        <p className="text-body-md mb-6 leading-relaxed">
          The Delhi Air Quality Risk Forecasting system is built on a PostgreSQL 16 relational data layer ingesting 105 government telemetry spreadsheets from CPCB and DPCC across 7 monitoring stations (2023–2026).
        </p>

        <h3 className="font-label-caps uppercase tracking-wider text-primary mb-2 mt-8">Modeling Approach</h3>
        <p className="text-body-md mb-6 leading-relaxed">
          Standard gradient boosting trees hit a hard mathematical ceiling during peak winter. A 50/50 hybrid model blending Naive Persistence with an L2-regularized linear Ridge regression on 49 curated causal features provides unbounded extrapolation into extreme pollution levels.
        </p>

        <h3 className="font-label-caps uppercase tracking-wider text-primary mb-2 mt-8">Risk Classification Protocol</h3>
        <p className="text-body-md mb-6 leading-relaxed">
          Continuous AQI forecasts are mapped to the 6 statutory CPCB categories (Good to Severe). Applying an asymmetric 5:1 loss ratio—penalizing a missed severe crisis five times more than a false alarm—lowers the optimal decision threshold from 401.0 to 341.5 AQI.
        </p>

        <div className="mt-8 p-space-md bg-surface-container-lowest border border-error/20 rounded relative overflow-hidden">
          <div className="absolute top-0 left-0 w-1 h-full bg-error"></div>
          <h4 className="font-label-code text-error font-bold mb-2">Cost-Optimal Rule (τ = 341.5)</h4>
          <p className="text-body-sm text-on-surface-variant">
            Raises Severe recall from 61.08% to 95.71%, reducing missed hazardous hours from 1,568 down to 173 hours (an 89% reduction) out-of-sample.
          </p>
        </div>
      </div>
    </>
  );
}
