import React, { useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceArea,
  ReferenceLine
} from 'recharts';
import { format, parseISO } from 'date-fns';
import type { Horizon } from '../../types';
import { COST_OPTIMAL_THRESHOLD } from '../../lib/thresholds';

interface AQITrajectoryChartProps {
  data: any[];
  horizon: Horizon;
  isLoading: boolean;
}

export function AQITrajectoryChart({ data, horizon, isLoading }: AQITrajectoryChartProps) {
  // Format data for Recharts
  const chartData = useMemo(() => {
    if (!data || data.length === 0) return [];

    return data.map((row: any) => {
      let actual = 0;
      let predicted = 0;
      let naive = 0;

      if (horizon === '24h') {
        actual = row.target_aqi_24h || null;
        predicted = row.prediction_hybrid_6c_winning || null;
        naive = row.prediction_naive_persistence || null;
      } else {
        actual = row.y_true || null;
        predicted = row.y_pred || null;
        naive = row.naive_pred || null;
      }

      return {
        timestamp_raw: row.timestamp,
        time: format(parseISO(row.timestamp), 'dd MMM HH:mm'),
        Actual: actual,
        Model: predicted,
        Baseline: naive
      };
    });
  }, [data, horizon]);

  if (isLoading) {
    return (
      <div className="h-[400px] w-full flex items-center justify-center animate-pulse bg-surface-container-low/20 rounded">
        <span className="font-label-code text-on-surface-variant">Loading model trajectories...</span>
      </div>
    );
  }

  if (chartData.length === 0) {
    return (
      <div className="h-[400px] w-full flex items-center justify-center bg-surface-container-low/20 rounded border border-error/20">
        <span className="font-label-code text-error">No forecast data available for this station.</span>
      </div>
    );
  }

  return (
    <div className="h-[400px] w-full p-2 font-label-code text-[11px]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />

          <XAxis
            dataKey="time"
            stroke="rgba(255,255,255,0.4)"
            tick={{ fill: 'rgba(255,255,255,0.4)' }}
            minTickGap={40}
          />
          <YAxis
            stroke="rgba(255,255,255,0.4)"
            tick={{ fill: 'rgba(255,255,255,0.4)' }}
            domain={[0, 500]}
          />

          <Tooltip
            contentStyle={{
              backgroundColor: 'rgba(1, 15, 31, 0.95)',
              borderColor: 'rgba(255,255,255,0.1)',
              borderRadius: '4px',
              color: '#fff',
              boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.5)'
            }}
            itemStyle={{ fontWeight: 'bold' }}
          />

          {/* Background ranges representing CPCB categories */}
          <ReferenceArea y1={0} y2={50} fill="#10B981" fillOpacity={0.02} />
          <ReferenceArea y1={51} y2={100} fill="#10B981" fillOpacity={0.03} />
          <ReferenceArea y1={101} y2={200} fill="#F59E0B" fillOpacity={0.03} />
          <ReferenceArea y1={201} y2={300} fill="#F97316" fillOpacity={0.05} />
          <ReferenceArea y1={301} y2={400} fill="#F43F5E" fillOpacity={0.05} />
          <ReferenceArea y1={400} y2={500} fill="#A855F7" fillOpacity={0.08} />

          {/* Cost-Optimal Threshold line */}
          <ReferenceLine
            y={COST_OPTIMAL_THRESHOLD}
            stroke="#ffb4ab"
            strokeDasharray="4 4"
            label={{ value: `τ=${COST_OPTIMAL_THRESHOLD}`, position: 'insideTopLeft', fill: '#ffb4ab', fontSize: 10 }}
          />

          <Line
            type="monotone"
            dataKey="Actual"
            stroke="#ffffff"
            strokeWidth={1.5}
            dot={false}
            strokeOpacity={0.3}
          />
          <Line
            type="monotone"
            dataKey="Baseline"
            stroke="#ffb95f"
            strokeWidth={1.5}
            dot={false}
            strokeOpacity={0.6}
            strokeDasharray="4 2"
          />
          <Line
            type="monotone"
            dataKey="Model"
            stroke="#4edea3"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
