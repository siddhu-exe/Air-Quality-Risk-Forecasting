import React from 'react';
import { useAppStore } from '../../store';
import { cn } from '../../lib/utils';
import type { Horizon } from '../../types';

export function HorizonSelector({ className }: { className?: string }) {
  const { horizon, setHorizon } = useAppStore();

  const getButtonClass = (value: Horizon) => {
    const isActive = horizon === value;
    if (isActive) {
      // Based on prototype active state
      if (value === '24h') {
        return "px-space-sm py-0.5 bg-error-container/20 text-error rounded font-bold border border-error/30";
      }
      return "px-space-sm py-0.5 bg-surface-container-lowest text-primary rounded font-bold border border-primary/30";
    }
    // Inactive state
    if (value === '24h') {
      return "px-space-sm py-0.5 text-error/70 hover:text-error border border-transparent";
    }
    return "px-space-sm py-0.5 text-on-surface-variant hover:text-on-surface border border-transparent";
  };

  return (
    <div className={cn("flex items-center bg-surface-container-high rounded p-1 font-label-code text-label-code", className)}>
      <button
        onClick={() => setHorizon('1h')}
        className={getButtonClass('1h')}
        type="button"
      >
        1h
      </button>
      <button
        onClick={() => setHorizon('6h')}
        className={getButtonClass('6h')}
        type="button"
      >
        6h
      </button>
      <button
        onClick={() => setHorizon('24h')}
        className={getButtonClass('24h')}
        type="button"
      >
        24h
      </button>
    </div>
  );
}
