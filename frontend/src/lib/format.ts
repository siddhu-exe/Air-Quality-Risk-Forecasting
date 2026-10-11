/** All display times are Asia/Kolkata (IST); the API sends ISO 8601 with an offset. */
const IST = 'Asia/Kolkata'
const MINUS = '−'

const clockFormat = new Intl.DateTimeFormat('en-GB', {
  timeZone: IST,
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
})

const dayFormat = new Intl.DateTimeFormat('en-GB', {
  timeZone: IST,
  weekday: 'short',
  day: 'numeric',
  month: 'short',
})

function toDate(iso: string): Date {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) throw new RangeError(`Invalid date: ${iso}`)
  return date
}

function parts(format: Intl.DateTimeFormat, date: Date): Record<string, string> {
  const out: Record<string, string> = {}
  for (const p of format.formatToParts(date)) out[p.type] = p.value
  return out
}

/** "14:00" */
export function formatClock(iso: string): string {
  const p = parts(clockFormat, toDate(iso))
  return `${p.hour}:${p.minute}`
}

/** "Sun 11 Oct" */
export function formatDay(iso: string): string {
  const p = parts(dayFormat, toDate(iso))
  return `${p.weekday} ${p.day} ${p.month}`
}

/** "Mon 14:00" */
export function formatWeekdayClock(iso: string): string {
  const p = parts(dayFormat, toDate(iso))
  return `${p.weekday} ${formatClock(iso)}`
}

/** "Updated 14:00 IST · Sun 11 Oct" */
export function formatUpdated(iso: string): string {
  return `Updated ${formatClock(iso)} IST · ${formatDay(iso)}`
}

/** 0.314 -> "31%". */
export function formatPercent(fraction: number): string {
  return `${Math.round(fraction * 100)}%`
}

/** Integer with an explicit sign and a true minus: +18, −4, 0. */
export function formatSigned(value: number): string {
  const rounded = Math.round(value)
  if (rounded === 0) return '0'
  return rounded > 0 ? `+${rounded}` : `${MINUS}${Math.abs(rounded)}`
}

/** Two-decimal skill index with sign: +0.09, −0.03. */
export function formatSkillIndex(value: number): string {
  const fixed = Math.abs(value).toFixed(2)
  if (Number(fixed) === 0) return '0.00'
  return value > 0 ? `+${fixed}` : `${MINUS}${fixed}`
}

/** "5 min", "2 h 14 min" for a duration in milliseconds. */
export function formatAge(ms: number): string {
  const minutes = Math.max(0, Math.round(ms / 60_000))
  if (minutes < 60) return `${minutes} min`
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return m === 0 ? `${h} h` : `${h} h ${m} min`
}

/** Milliseconds between two ISO timestamps (later minus earlier). */
export function msBetween(laterIso: string, earlierIso: string): number {
  return toDate(laterIso).getTime() - toDate(earlierIso).getTime()
}

/** Hours from `fromIso` to `toIso`, e.g. -72 or 24. */
export function hoursBetween(toIso: string, fromIso: string): number {
  return msBetween(toIso, fromIso) / 3_600_000
}
