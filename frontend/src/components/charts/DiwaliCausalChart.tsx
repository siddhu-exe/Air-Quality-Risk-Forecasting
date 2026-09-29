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
import { format, parseISO } from 'date-fns';

interface DiwaliCausalChartProps {
  data: any[];
  isLoading: boolean;
}

export function DiwaliCausalChart({ data, isLoading }: DiwaliCausalChartProps) {
  const chartData = useMemo(() => {
    if (!data || data.length === 0) return [];

    // Group by timestamp and take mean across stations, or just use one station if available.
    // Let's assume the CSV provides a time series. We can average across stations or just aggregate it.
    // Realistically, the Streamlit app probably aggregates this.
    // For now, let's just use the rows as they are if it's already aggregated, or take the first station's data.

    const aggregated = data.reduce((acc: any, row: any) => {
      const time = format(parseISO(row.timestamp), 'dd MMM HH:mm');
      if (!acc[time]) {
        acc[time] = { time, timestamp: row.timestamp, pm25: 0, aqi: 0, count: 0, event_name: row.event_name };
      }
      acc[time].pm25 += row.pm25 || 0;
      acc[time].aqi += row.aqi || 0;
      acc[time].count += 1;
      return acc;
    }, {});

    const sortedData = Object.values(aggregated).map((d: any) => ({
      ...d,
      PM25: d.pm25 / d.count,
      AQI: d.aqi / d.count,
    })).sort((a: any, b: any) => a.timestamp.localeCompare(b.timestamp));

    return sortedData;
  }, [data]);

  if (isLoading) {
    return (
      <div className="h-full w-full flex items-center justify-center animate-pulse">
        <span className="font-label-code text-on-surface-variant">Computing counterfactuals...</span>
      </div>
    );
  }

  if (chartData.length === 0) {
    return (
      <div className="h-full w-full flex items-center justify-center">
        <span className="font-label-code text-error">No causal data available.</span>
      </div>
    );
  }

  // Find where Diwali actually happened (if event_name contains Diwali)
  const diwaliEvent = chartData.find((d: any) => d.event_name === 'Diwali');
  const referenceTime = diwaliEvent ? diwaliEvent.time : chartData[Math.floor(chartData.length / 2)]?.time;

  return (
    <div className="h-full w-full p-2 font-label-code text-[11px]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 20, right: 20, left: -10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />

          <XAxis
            dataKey="time"
            stroke="rgba(255,255,255,0.4)"
            tick={{ fill: 'rgba(255,255,255,0.4)' }}
            minTickGap={40}
          />
          <YAxis
            yAxisId="left"
            stroke="rgba(255,255,255,0.4)"
            tick={{ fill: 'rgba(255,255,255,0.4)' }}
          />

          <Tooltip
            contentStyle={{
              backgroundColor: 'rgba(1, 15, 31, 0.95)',
              borderColor: 'rgba(255,255,255,0.1)',
              borderRadius: '4px',
              color: '#fff'
            }}
            itemStyle={{ fontWeight: 'bold' }}
          />

          <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />

          {referenceTime && (
            <ReferenceLine
              x={referenceTime}
              stroke="#ffb4ab"
              strokeDasharray="3 3"
              label={{ value: 'Diwali Ban Nullified', position: 'insideTopLeft', fill: '#ffb4ab', fontSize: 10 }}
            />
          )}

          <Line
            yAxisId="left"
            type="monotone"
            name="Observed AQI"
            dataKey="AQI"
            stroke="#ffffff"
            strokeWidth={2}
            dot={false}
          />

          <Line
            yAxisId="left"
            type="monotone"
            name="PM2.5 (Tracer)"
            dataKey="PM25"
            stroke="#ffb95f"
            strokeWidth={1.5}
            strokeDasharray="4 4"
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
