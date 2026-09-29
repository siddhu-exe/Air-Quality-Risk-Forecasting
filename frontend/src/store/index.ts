import { create } from 'zustand';
import type { Horizon } from '../types';

interface AppState {
  horizon: Horizon;
  setHorizon: (horizon: Horizon) => void;

  activeStationId: string;
  setActiveStation: (id: string) => void;
}

export const useAppStore = create<AppState>((set) => ({
  horizon: '1h',
  setHorizon: (horizon) => set({ horizon }),

  activeStationId: 'ALL', // Or specific default like 'Anand Vihar'
  setActiveStation: (id) => set({ activeStationId: id }),
}));
