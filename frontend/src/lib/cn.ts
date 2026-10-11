import { clsx, type ClassValue } from 'clsx'
import { extendTailwindMerge } from 'tailwind-merge'

/**
 * The pixel-named type scale (`text-13`, `text-136`...) must be registered as
 * font sizes. Left alone, tailwind-merge reads `text-13` as a colour and drops
 * it whenever a colour class such as `text-ink-muted` follows.
 */
const FONT_SIZES = ['11', '12', '13', '14', '15', '16', '17', '22', '24', '26', '28', '30', '32', '34', '36', '40', '56', '64', '96', '136']

const twMerge = extendTailwindMerge({
  extend: { classGroups: { 'font-size': [{ text: FONT_SIZES }] } },
})

/** Joins class names and resolves conflicting Tailwind utilities (last wins). */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}
