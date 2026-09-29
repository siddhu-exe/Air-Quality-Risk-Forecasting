import React from 'react';
import { cn } from '../../lib/utils';
import type { GRAPStage } from '../../types';

interface GRAPBannerProps {
  stage: GRAPStage;
  probability: number;
  className?: string;
}

export function GRAPBanner({ stage, probability, className }: GRAPBannerProps) {
  if (stage === 'NONE') return null;

  return (
    <div className={cn("w-full bg-error-container/20 px-margin-desktop py-1 flex items-center justify-between border-b border-error/20", className)}>
      <div className="flex items-center gap-space-xs">
        <span className="material-symbols-outlined text-error text-[16px]">warning</span>
        <span className="font-label-code text-label-code text-error font-bold uppercase">{stage} Warning:</span>
        <span className="font-label-code text-label-code text-on-surface">
          P(AQI &gt; 400 in 24h) = <span className="text-error font-bold">{(probability * 100).toFixed(1)}%</span>
        </span>
      </div>
      <div className="hidden md:flex items-center gap-space-md">
        <span className="font-label-code text-label-code text-tertiary font-bold uppercase">Critical Threshold Imminent</span>
        <span className="px-space-xs py-0.5 rounded bg-error text-on-error font-label-caps text-label-caps font-bold">CAQM-382</span>
      </div>
    </div>
  );
}
