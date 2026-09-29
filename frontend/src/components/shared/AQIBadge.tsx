import React from 'react';
import { cn } from '../../lib/utils';
import { type AQICategory, type GRAPStage } from '../../types';
import { getAQIColorClass } from '../../lib/aqi';

interface AQIBadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  value?: number;
  category?: AQICategory | GRAPStage;
  label?: string;
  variant?: 'outline' | 'solid' | 'subtle';
}

export function AQIBadge({
  value,
  category,
  label,
  variant = 'subtle',
  className,
  ...props
}: AQIBadgeProps) {
  const displayLabel = label || category || (value ? value.toString() : '');
  const colorPrefix = category ? getAQIColorClass(category, 'text') : 'text-primary';
  const bgPrefix = category ? getAQIColorClass(category, 'bg') : 'bg-primary';

  // Custom subtle variants for the dashboard: 15% opacity with 40% border
  let variantClasses = '';
  if (variant === 'subtle') {
    // We map to tailwind class combinations manually since arbitrary opacity requires mapping
    const baseColorName = bgPrefix.replace('bg-', ''); // e.g. primary, error
    variantClasses = `bg-${baseColorName}/15 border border-${baseColorName}/40 text-${baseColorName}`;
  } else if (variant === 'solid') {
    variantClasses = `${bgPrefix} text-on-${bgPrefix.replace('bg-', '')} border border-transparent`;
  } else {
    variantClasses = `bg-transparent border border-${bgPrefix.replace('bg-', '')} ${colorPrefix}`;
  }

  return (
    <span
      className={cn(
        "px-space-xs py-0.5 rounded font-label-caps text-label-caps font-bold uppercase inline-flex items-center justify-center",
        variantClasses,
        className
      )}
      {...props}
    >
      {displayLabel}
    </span>
  );
}
