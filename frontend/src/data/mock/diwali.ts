export const mockDiwaliHourly = Array.from({ length: 48 }).map((_, i) => ({
  hour: i,
  pm25: i === 20 ? 960.7 : 120 + Math.random() * 50, // Spike at hour 20
  so2: i === 20 ? 73.5 : 10 + Math.random() * 5,
  is_diwali: i >= 18 && i <= 24
}));

export const mockDiwaliRegression = {
  net_pyro_spike: 142.5,
  p_value: 0.001,
  actual_peak: 360,
  counterfactual_peak: 218
};
