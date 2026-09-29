export const mockThresholdSweep = Array.from({ length: 40 }).map((_, i) => {
  const threshold = 200 + i * 5;
  const severeRecall = threshold === 341.5 ? 0.9571 : Math.max(0, 1 - (threshold - 200) / 300);
  const falseAlarms = Math.max(0, 5000 - (threshold - 200) * 20); // made up stats

  return {
    threshold,
    severeRecall,
    falseAlarms
  };
});
