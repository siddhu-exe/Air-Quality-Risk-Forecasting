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

const dateKeyFormat = new Intl.DateTimeFormat('en-CA', {
  timeZone: IST,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
})

/** Whole IST calendar days from `fromIso` to `toIso` (0 = same day, 1 = next day). */
function calendarDaysBetween(toIso: string, fromIso: string): number {
  const asUtcDay = (iso: string): number => {
    const p = parts(dateKeyFormat, toDate(iso))
    return Date.UTC(Number(p.year), Number(p.month) - 1, Number(p.day))
  }
  return Math.round((asUtcDay(toIso) - asUtcDay(fromIso)) / 86_400_000)
}

/** "15:00 today", "14:00 tomorrow", else "Wed 14:00", judged on the IST calendar. */
export function formatWhen(iso: string, referenceIso: string): string {
  const days = calendarDaysBetween(iso, referenceIso)
  if (days === 0) return `${formatClock(iso)} today`
  if (days === 1) return `${formatClock(iso)} tomorrow`
  return formatWeekdayClock(iso)
}

/**
 * A rate as a percentage that never rounds up to a claim it does not make:
 * 99.8% stays "99.8%" (not "100%"), and only an exact 1 reads "100%".
 */
export function formatRate(fraction: number): string {
  const pct = fraction * 100
  if (fraction > 0.99 && fraction < 1) return `${(Math.floor(pct * 10) / 10).toFixed(1)}%`
  if (fraction > 0 && fraction < 0.005) return '<1%'
  return `${Math.round(pct)}%`
}

/** 1568 -> "1,568". */
export function formatCount(n: number): string {
  return n.toLocaleString('en-IN')
}
