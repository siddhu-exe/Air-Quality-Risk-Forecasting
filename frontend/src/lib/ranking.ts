const COUNT_WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine']

/** 2 -> "two", 12 -> "12": small counts read better as words in prose. */
export function countWord(n: number): string {
  return COUNT_WORDS[n] ?? String(n)
}
