import React from 'react';
import { cn } from '../../lib/utils';

export function PanelHeader({ title, badge, className }: { title: string, badge?: React.ReactNode, className?: string }) {
  return (
    <div className={cn("flex flex-wrap flex-row items-center justify-between gap-space-md pb-space-sm border-b border-surface-container-high/40", className)}>
      <h2 className="font-headline-sm text-headline-sm text-on-surface font-bold tracking-tight">{title}</h2>
      {badge && (
        <span className="px-space-xs py-0.5 rounded bg-surface-container-high text-primary font-label-code text-label-code font-semibold">
          {badge}
        </span>
      )}
    </div>
  );
}

export function SectionHeader({ title, subtitle, className }: { title: string, subtitle?: string, className?: string }) {
  return (
    <div className={cn("flex items-center gap-space-md py-space-xs text-on-surface-variant font-label-code text-label-code border-b border-surface-container-high/40", className)}>
      <div className="flex items-center gap-space-xs">
        <span className="w-2 h-2 rounded-full bg-primary animate-pulse"></span>
        <span className="text-primary font-bold">{title}</span>
      </div>
      {subtitle && <span>{subtitle}</span>}
    </div>
  );
}
