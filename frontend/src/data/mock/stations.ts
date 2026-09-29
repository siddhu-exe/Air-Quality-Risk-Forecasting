import type { Station } from '../../types';

export const mockStations: Station[] = [
  { id: '1', name: 'Anand Vihar', aqi: 442, status: 'LIVE' },
  { id: '2', name: 'ITO', aqi: 384, status: 'LIVE' },
  { id: '3', name: 'Punjabi Bagh', aqi: 412, status: 'LIVE' },
  { id: '4', name: 'RK Puram', aqi: 368, status: 'LIVE' },
  { id: '5', name: 'Mandir Marg', aqi: 280, status: 'LIVE' },
  { id: '6', name: 'Dwarka', aqi: 310, status: 'LIVE' },
  { id: '7', name: 'Okhla Phase 2', aqi: 0, status: 'CALIBRATING' },
];
