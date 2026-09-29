import React, { useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Legend
} from 'recharts';

interface CostThresholdChartProps {
  data: any[];
  isLoading: boolean;
  activeThreshold: number;
}

export function CostThresholdChart({ data, isLoading, activeThreshold }: CostThresholdChartProps) {
  const chartData = useMemo(() => {
    if (!data || data.length === 0) return [];

    // Sort by threshold ascending to make the X-axis linear
    return [...data].sort((a, b) => a.threshold - b.threshold).map(d => ({
      ...d,
      Precision: Number((d.precision * 100).toFixed(1)),
      Recall: Number((d.recall * 100).toFixed(1)),
      Cost5x: Number(d.cost_sample_5x || 0)
    }));
  }, [data]);

  if (isLoading) {
    return (
      <div className="h-full w-full flex items-center justify-center animate-pulse">
        <span className="font-label-code text-on-surface-variant">Computing asymmetric loss surfaces...</span>
      </div>
    );
  }

  if (chartData.length === 0) {
    return (
      <div className="h-full w-full flex items-center justify-center">
        <span className="font-label-code text-error">No threshold sweep data available.</span>
      </div>
    );
  }

  return (
    <div className="h-full w-full p-2 font-label-code text-[11px]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 20, right: 20, left: -20, bottom: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />

          {/* Threshold X-Axis */}
          <XAxis
            dataKey="threshold"
            type="number"
            domain={['dataMin', 'dataMax']}
            stroke="rgba(255,255,255,0.4)"
            tick={{ fill: 'rgba(255,255,255,0.4)' }}
            label={{ value: 'AQI Decision Threshold (τ)', position: 'insideBottom', offset: -15, fill: 'rgba(255,255,255,0.6)' }}
          />

          {/* Left Y-Axis: Percentages (Precision/Recall) */}
          <YAxis
            yAxisId="left"
            domain={[0, 100]}
            stroke="rgba(255,255,255,0.4)"
            tick={{ fill: 'rgba(255,255,255,0.4)' }}
            tickFormatter={(val) => `${val}%`}
          />

          {/* Right Y-Axis: Cost (Arbitrary Units) */}
          <YAxis
            yAxisId="right"
            orientation="right"
            stroke="rgba(255,255,255,0.4)"
            tick={{ fill: 'rgba(255,255,255,0.4)' }}
            hide // hide it to keep chart clean if needed, or show it so users understand the cost curve
          />

          <Tooltip
            contentStyle={{
              backgroundColor: 'rgba(1, 15, 31, 0.95)',
              borderColor: 'rgba(255,255,255,0.1)',
              borderRadius: '4px',
              color: '#fff'
            }}
            itemStyle={{ fontWeight: 'bold' }}
            labelFormatter={(val) => `Threshold: ${val} AQI`}
          />

          <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />

          <ReferenceLine
            yAxisId="left"
            x={activeThreshold}
            stroke="#4edea3"
            strokeDasharray="4 4"
            label={{ value: 'Active τ', position: 'insideTopLeft', fill: '#4edea3', fontSize: 10 }}
          />

          <Line yAxisId="left" type="monotone" name="Recall (Catch Crises)" dataKey="Recall" stroke="#ffb4ab" strokeWidth={2} dot={false} />
          <Line yAxisId="left" type="monotone" name="Precision (Avoid False Alarms)" dataKey="Precision" stroke="#4edea3" strokeWidth={2} dot={false} />
          <Line yAxisId="right" type="monotone" name="Relative Cost (5:1 Asymmetric)" dataKey="Cost5x" stroke="#A855F7" strokeWidth={2} strokeDasharray="5 5" dot={false} strokeOpacity={0.6} />

        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
