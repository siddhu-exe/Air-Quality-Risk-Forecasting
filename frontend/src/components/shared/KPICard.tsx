import React from 'react';
import { cn } from '../../lib/utils';

interface KPICardProps extends React.HTMLAttributes<HTMLDivElement> {
  title: string;
  badge?: React.ReactNode;
  children: React.ReactNode;
}

export function KPICard({ title, badge, children, className, ...props }: KPICardProps) {
  return (
    <div
      className={cn(
        "rounded bg-surface-container p-space-md shadow-sm border border-surface-container-high/60 flex flex-col justify-between",
        className
      )}
      {...props}
    >
      <div className="flex items-center justify-between pointer-events-none">
        <span className="font-label-caps text-label-caps uppercase text-on-surface-variant">
          {title}
        </span>
        {badge}
      </div>
      {children}
    </div>
  );
}
