/** Stations from worst to best tomorrow; ties keep the API's order. */
export function rankByForecast<T extends { forecast24h: number }>(stations: readonly T[]): T[] {
  return [...stations].sort((a, b) => b.forecast24h - a.forecast24h)
}

const COUNT_WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine']

/** 2 -> "two", 12 -> "12": small counts read better as words in prose. */
export function countWord(n: number): string {
  return COUNT_WORDS[n] ?? String(n)
}
