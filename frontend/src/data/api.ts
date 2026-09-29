import { useQuery } from '@tanstack/react-query';
import type { Station, Horizon } from '../types';

// Depending on the environment, VITE_API_URL could be set,
// But we have proxy configured in vite.config.ts for /api
const API_BASE = '/api';

export function useStations() {
  return useQuery<Station[]>({
    queryKey: ['stations'],
    queryFn: async () => {
      const response = await fetch(`${API_BASE}/stations`);
      if (!response.ok) throw new Error('Failed to fetch stations');
      return response.json();
    }
  });
}

export function useForecasts(horizon: Horizon, stationId: string = 'ALL') {
  return useQuery({
    queryKey: ['forecasts', horizon, stationId],
    queryFn: async () => {
      const response = await fetch(`${API_BASE}/forecasts?horizon=${horizon}&station=${stationId}`);
      if (!response.ok) throw new Error('Failed to fetch forecasts');
      return response.json();
    }
  });
}

export function useDiwaliCausal() {
  return useQuery({
    queryKey: ['causal', 'diwali'],
    queryFn: async () => {
      const response = await fetch(`${API_BASE}/causal/diwali`);
      if (!response.ok) throw new Error('Failed to fetch diwali causal data');
      return response.json();
    }
  });
}

export function useThresholdSweep() {
  return useQuery({
    queryKey: ['thresholds', 'sweep'],
    queryFn: async () => {
      const response = await fetch(`${API_BASE}/thresholds/sweep`);
      if (!response.ok) throw new Error('Failed to fetch threshold sweep');
      return response.json();
    }
  });
}

export function useOperatingPoints() {
  return useQuery({
    queryKey: ['thresholds', 'operating-points'],
    queryFn: async () => {
      const response = await fetch(`${API_BASE}/thresholds/operating-points`);
      if (!response.ok) throw new Error('Failed to fetch operating points');
      return response.json();
    }
  });
}

export function useEpisodes() {
  return useQuery({
    queryKey: ['episodes'],
    queryFn: async () => {
      const response = await fetch(`${API_BASE}/episodes`);
      if (!response.ok) throw new Error('Failed to fetch episodes');
      return response.json();
    }
  });
}
