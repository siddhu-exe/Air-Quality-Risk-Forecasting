import React from 'react';
import { NavLink } from 'react-router-dom';
import { HorizonSelector } from '../shared/HorizonSelector';

export function TopBar() {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-surface-container-lowest/95 backdrop-blur-md shadow-[0_1px_8px_rgba(0,0,0,0.4)]">
      <div className="h-16 w-full px-margin-desktop flex items-center justify-between gap-space-lg">
        <div className="flex items-center gap-space-md shrink-0">
          <div className="flex items-center gap-space-xs">
            <span className="font-headline-sm text-headline-sm tracking-tight text-on-surface font-bold">VayuRisk AI</span>
            <span className="px-space-xs py-0.5 rounded bg-surface-container-high text-primary font-label-code text-label-code border border-surface-container-highest">Delhi NCR</span>
          </div>
        </div>
        <div className="hidden xl:flex items-center gap-space-md px-space-md py-1 bg-surface-container-low rounded border border-surface-container-high/50">
          <div className="flex items-center gap-space-xs">
            <span className="w-2 h-2 rounded-full bg-primary animate-pulse"></span>
            <span className="font-label-code text-label-code text-on-surface font-semibold">7 STATIONS</span>
          </div>
          <span className="text-outline-variant font-label-code text-label-code">|</span>
          <span className="font-label-code text-label-code text-primary font-semibold">SYNC: LIVE</span>
          <span className="text-outline-variant font-label-code text-label-code">|</span>
          <span className="font-label-code text-label-code text-on-surface-variant">LATENCY 2.4s</span>
        </div>
        <div className="flex items-center gap-space-md">
          <HorizonSelector />
          <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center shrink-0">
            <span className="material-symbols-outlined text-on-primary text-[18px]">person</span>
          </div>
        </div>
      </div>

      <div className="w-full bg-surface-container px-margin-desktop shadow-inner border-y border-surface-container-highest">
        <nav className="flex items-center gap-space-xs overflow-x-auto py-1">
          <NavLink
            to="/"
            className={({ isActive }) =>
              `px-space-md py-1 font-label-caps text-label-caps uppercase whitespace-nowrap transition-colors ${
                isActive
                  ? 'text-primary bg-surface-container-highest rounded font-bold'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`
            }
          >
            Real-Time & Forecasts
          </NavLink>
          <NavLink
            to="/performance"
            className={({ isActive }) =>
              `px-space-md py-1 font-label-caps text-label-caps uppercase whitespace-nowrap transition-colors ${
                isActive
                  ? 'text-primary bg-surface-container-highest rounded font-bold'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`
            }
          >
            Model Performance
          </NavLink>
          <NavLink
            to="/causal"
            className={({ isActive }) =>
              `px-space-md py-1 font-label-caps text-label-caps uppercase whitespace-nowrap transition-colors ${
                isActive
                  ? 'text-primary bg-surface-container-highest rounded font-bold'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`
            }
          >
            Causal Impact
          </NavLink>
          <NavLink
            to="/thresholds"
            className={({ isActive }) =>
              `px-space-md py-1 font-label-caps text-label-caps uppercase whitespace-nowrap transition-colors ${
                isActive
                  ? 'text-primary bg-surface-container-highest rounded font-bold'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`
            }
          >
            Risk Thresholds
          </NavLink>
          <NavLink
            to="/methodology"
            className={({ isActive }) =>
              `px-space-md py-1 font-label-caps text-label-caps uppercase whitespace-nowrap transition-colors ${
                isActive
                  ? 'text-primary bg-surface-container-highest rounded font-bold'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`
            }
          >
            Methodology
          </NavLink>
        </nav>
      </div>
    </header>
  );
}
