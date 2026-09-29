import React from 'react';
import { useStations } from '../../data/api';
import { getAQIColorClass, getAQICategory } from '../../lib/aqi';

export function Sidebar() {
  const { data: stations = [], isLoading, isError } = useStations();

  return (
    <aside className="fixed left-0 top-32 bottom-0 w-64 bg-surface-container-lowest z-40 flex flex-col justify-between py-space-md shadow-[1px_0_12px_rgba(0,0,0,0.5)] border-r border-surface-container-high/50">
      <div className="flex flex-col gap-space-md px-space-md overflow-y-auto">
        <div className="px-space-sm pt-space-xs">
          <span className="font-label-caps text-label-caps text-on-surface-variant uppercase tracking-wider">Active Telemetry Hub</span>
        </div>
        <div className="flex flex-col gap-space-2xs">
          {isLoading ? (
            <div className="text-on-surface-variant font-label-code text-label-code px-space-sm animate-pulse">Loading stations...</div>
          ) : isError ? (
            <div className="text-error font-label-code text-label-code px-space-sm">Data Engine Offline</div>
          ) : stations.map((station) => (
            <div key={station.id} className="px-space-sm py-space-xs rounded bg-surface-container-low flex items-center justify-between border border-surface-container-high/30">
              <span className="font-label-code text-label-code text-on-surface-variant">{station.name}</span>
              {station.status === 'LIVE' ? (
                <span className={`font-label-code text-label-code font-semibold ${getAQIColorClass(getAQICategory(station.aqi || 0), 'text')}`}>
                  {station.aqi || '--'} AQI
                </span>
              ) : (
                <span className="font-label-code text-label-code text-primary/70 font-semibold text-[10px] tracking-wider">{station.status}</span>
              )}
            </div>
          ))}
        </div>
        <div className="px-space-sm pt-space-sm">
          <span className="font-label-caps text-label-caps text-on-surface-variant uppercase tracking-wider">Mitigation Status</span>
        </div>
        <div className="p-space-sm rounded bg-surface-container flex flex-col gap-space-2xs border border-surface-container-high/40">
          <div className="flex items-center justify-between">
            <span className="font-label-code text-label-code text-on-surface">GRAP II Active</span>
            <span className="w-2 h-2 rounded-full bg-secondary"></span>
          </div>
          <div className="flex items-center justify-between mt-1">
            <span className="font-label-code text-label-code text-on-surface-variant text-[10px]">Escalation Alert</span>
            <span className="font-label-code text-label-code text-error bg-error/10 px-1 py-0.5 rounded border border-error/20">STAGE III</span>
          </div>
        </div>
      </div>
      <div className="px-space-md flex flex-col gap-space-2xs">
        <div className="p-space-sm rounded bg-surface-container-high/30 flex flex-col gap-space-2xs border border-surface-container-high/40">
          <span className="font-label-caps text-label-caps text-on-surface-variant uppercase">Data Engine</span>
          <div className="flex items-center justify-between">
            <span className="font-label-code text-label-code text-on-surface-variant">CPCB + IMD + MODIS</span>
            <span className="font-label-code text-label-code text-primary font-bold">READY</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
