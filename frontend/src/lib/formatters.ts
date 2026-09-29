import { format, parseISO } from 'date-fns';
import { toZonedTime } from 'date-fns-tz';

const KOLKATA_TZ = 'Asia/Kolkata';

export function formatDateTime(isoString: string): string {
  if (!isoString) return '';
  const date = parseISO(isoString);
  const zonedDate = toZonedTime(date, KOLKATA_TZ);
  return format(zonedDate, 'dd MMM yyyy HH:mm');
}

export function formatTime(isoString: string): string {
  if (!isoString) return '';
  const date = parseISO(isoString);
  const zonedDate = toZonedTime(date, KOLKATA_TZ);
  return format(zonedDate, 'HH:mm');
}
