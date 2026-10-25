/**
 * Utility functions and helpers
 * This module contains reusable utility functions used throughout the application
 */

/**
 * Validates email format
 * @param value - The email string to validate
 * @returns True if email is valid, false otherwise
 */
export function validateEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

/**
 * Converts date format from MM/DD/YYYY to YYYY-MM-DD
 * @param dateString - Date string in MM/DD/YYYY format
 * @returns Date string in YYYY-MM-DD format or undefined
 */
export function convertDateFormat(dateString: string): string | undefined {
  if (!dateString) return undefined;
  
  const parts = dateString.split('/');
  if (parts.length === 3) {
    const month = parts[0].padStart(2, '0');
    const day = parts[1].padStart(2, '0');
    const year = parts[2];
    return `${year}-${month}-${day}`;
  }
  
  return undefined;
}

/**
 * Parses a datetime string from the backend as UTC.
 * The API serializes naive UTC datetimes without a timezone suffix
 * (e.g. "2026-06-23T12:00:00"). New Date() treats such strings as
 * local time, which silently shifts the displayed time by the
 * browser's UTC offset. Append 'Z' so it's parsed as UTC, unless an
 * offset is already present.
 * @param dateStr - The datetime string returned by the API
 * @returns A Date representing the correct UTC instant
 */
export function parseServerDate(dateStr: string): Date {
  const hasTimezone = /Z$|[+-]\d\d:?\d\d$/.test(dateStr);
  return new Date(hasTimezone ? dateStr : `${dateStr}Z`);
}

/*
 * Clinic time.
 * Every clinic (tenant) has its own IANA time zone, sent at login. All times are shown, and all booking
 * grids laid out, in the clinic's zone - never the viewer's browser zone - so a patient travelling, or
 * a support agent working remotely, sees the same 9:00 AM the doctor does. Calendar days are plain
 * {year, month, day} values, so no Date round-trip can shift them across zones.
 */

/** Clinic zone before sign-in, or if the server sent none. Same default as the backend (CLINIC_TIMEZONE). */
export const DEFAULT_CLINIC_TIMEZONE = 'America/New_York';

/** The viewer's own time zone (e.g. the default offered when setting up a clinic). */
export function browserTimeZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || DEFAULT_CLINIC_TIMEZONE;
  } catch {
    return DEFAULT_CLINIC_TIMEZONE;
  }
}

/** IANA zones this browser knows, for picking a clinic's zone; always includes `current`. */
export function supportedTimeZones(current: string): string[] {
  const supportedValuesOf = (Intl as unknown as { supportedValuesOf?: (key: string) => string[] }).supportedValuesOf;
  const zones = supportedValuesOf ? supportedValuesOf('timeZone') : [];
  return zones.includes(current) ? zones : [current, ...zones];
}

/** A calendar date with no time of day or zone; month is 1-12. */
export interface CalendarDay {
  year: number;
  month: number;
  day: number;
}

export interface ZonedParts extends CalendarDay {
  hour: number;
  minute: number;
}

const pad2 = (n: number) => String(n).padStart(2, '0');
const partsFormatters = new Map<string, Intl.DateTimeFormat>();

/** The wall-clock date and time an instant shows in `timeZone`. */
export function zonedParts(date: Date, timeZone: string): ZonedParts {
  let formatter = partsFormatters.get(timeZone);
  if (!formatter) {
    formatter = new Intl.DateTimeFormat('en-US', {
      timeZone, year: 'numeric', month: 'numeric', day: 'numeric', hour: 'numeric', minute: 'numeric', hourCycle: 'h23',
    });
    partsFormatters.set(timeZone, formatter);
  }
  const parts: Record<string, number> = {};
  for (const part of formatter.formatToParts(date)) {
    if (part.type !== 'literal') parts[part.type] = Number(part.value);
  }
  return { year: parts.year, month: parts.month, day: parts.day, hour: parts.hour % 24, minute: parts.minute };
}

/** The instant at which `timeZone` shows `day` at `hour`:00 (DST-safe). */
export function zonedTimeToDate(day: CalendarDay, hour: number, timeZone: string): Date {
  const wall = Date.UTC(day.year, day.month - 1, day.day, hour);
  let guess = wall;
  // Two corrections settle the zone's offset, including on daylight-saving change days
  for (let i = 0; i < 2; i++) {
    const shown = zonedParts(new Date(guess), timeZone);
    guess += wall - Date.UTC(shown.year, shown.month - 1, shown.day, shown.hour, shown.minute);
  }
  return new Date(guess);
}

/** Today's date in the clinic's zone. */
export function clinicToday(timeZone: string, now: Date = new Date()): CalendarDay {
  const { year, month, day } = zonedParts(now, timeZone);
  return { year, month, day };
}

export function addDays(day: CalendarDay, days: number): CalendarDay {
  const d = new Date(Date.UTC(day.year, day.month - 1, day.day + days));
  return { year: d.getUTCFullYear(), month: d.getUTCMonth() + 1, day: d.getUTCDate() };
}

/** 0 = Sunday ... 6 = Saturday. */
export function weekdayOf(day: CalendarDay): number {
  return new Date(Date.UTC(day.year, day.month - 1, day.day)).getUTCDay();
}

/** Monday of the week containing `day` (clinic weeks run Monday to Sunday). */
export function mondayOf(day: CalendarDay): CalendarDay {
  return addDays(day, -((weekdayOf(day) + 6) % 7));
}

export function sameDay(a: CalendarDay, b: CalendarDay): boolean {
  return a.year === b.year && a.month === b.month && a.day === b.day;
}

/** "2026-10-22" */
export function dayKey(day: CalendarDay): string {
  return `${String(day.year).padStart(4, '0')}-${pad2(day.month)}-${pad2(day.day)}`;
}

/** Formats a calendar day (no zone involved), e.g. { weekday: 'short', month: 'short', day: 'numeric' }. */
export function formatDay(day: CalendarDay, options: Intl.DateTimeFormatOptions): string {
  return new Date(Date.UTC(day.year, day.month - 1, day.day, 12)).toLocaleDateString('en-US', { ...options, timeZone: 'UTC' });
}

/** Formats an instant (Date or API timestamp) as clinic wall-clock time. */
export function formatInZone(value: Date | string, timeZone: string, options: Intl.DateTimeFormatOptions): string {
  const date = typeof value === 'string' ? parseServerDate(value) : value;
  return date.toLocaleString('en-US', { ...options, timeZone });
}

/**
 * Formats an API timestamp for display in clinic time
 * @param timeStr - The time string to format
 * @param timeZone - The clinic's IANA time zone
 * @returns Formatted date string
 */
export function formatTime(timeStr: string, timeZone: string): string {
  return formatInZone(timeStr, timeZone, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

/** Short zone name at `date`, e.g. "PDT", "EST" or "GMT+5:30". */
export function timeZoneAbbreviation(timeZone: string, date: Date = new Date()): string {
  const part = new Intl.DateTimeFormat('en-US', { timeZone, timeZoneName: 'short' }).formatToParts(date).find(p => p.type === 'timeZoneName');
  return part?.value ?? timeZone;
}

/** Note shown with schedules, e.g. "All times are clinic time: PDT (America/Los Angeles)". */
export function clinicTimeNote(timeZone: string, date: Date = new Date()): string {
  return `All times are clinic time: ${timeZoneAbbreviation(timeZone, date)} (${timeZone.replace(/_/g, ' ')})`;
}

/**
 * Gets today's date in the clinic's zone in MM/DD/YYYY format
 * @returns Today's date formatted as MM/DD/YYYY
 */
export function getTodayFormatted(timeZone: string = DEFAULT_CLINIC_TIMEZONE): string {
  const today = clinicToday(timeZone);
  return `${pad2(today.month)}/${pad2(today.day)}/${today.year}`;
}

/**
 * Parses error messages from API responses
 * @param error - The error object or message
 * @returns Clean error message string
 */
export function parseErrorMessage(error: unknown): string {
  let errorMessage = "An error occurred";
  
  if (error instanceof Error) {
    errorMessage = error.message;
    // If it's still in JSON format, extract the detail
    if (errorMessage.startsWith("{")) {
      try {
        const errorData = JSON.parse(errorMessage);
        errorMessage = errorData.detail || errorMessage;
      } catch {
        // Keep original message if parsing fails
      }
    }
  }
  
  return errorMessage;
}

/**
 * Creates a delay using setTimeout
 * @param ms - Milliseconds to delay
 * @returns Promise that resolves after the delay
 */
export function delay(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * First and last hourly office slots in clinic local time (24-hour clock): 8 AM through the 11 PM slot.
 * The same hours apply in every clinic's own zone.
 * Keep in sync with WORKDAY_FIRST_SLOT_HOUR / WORKDAY_LAST_SLOT_HOUR in backend/app/core/timeutils.py.
 */
export const WORKDAY_FIRST_SLOT_HOUR = 8;
export const WORKDAY_LAST_SLOT_HOUR = 23;

/** Hourly slot labels ("8:00 AM" ... "11:00 PM") for the availability and booking grids. */
export const OFFICE_HOUR_SLOTS: string[] = Array.from(
  { length: WORKDAY_LAST_SLOT_HOUR - WORKDAY_FIRST_SLOT_HOUR + 1 },
  (_, i) => {
    const hour = WORKDAY_FIRST_SLOT_HOUR + i;
    return `${hour % 12 === 0 ? 12 : hour % 12}:00 ${hour < 12 ? 'AM' : 'PM'}`;
  }
);

/** Search text that lists everyone (of the chosen role) on the search screens. */
export const SEARCH_WILDCARD = "*";

/**
 * Problem with a people-search query, or "" if it can be sent: at least 2 characters, or "*" for everyone.
 * @param what - What can be searched, e.g. "a name or phone number"
 */
export function searchQueryProblem(query: string, what: string): string {
  const q = query.trim();
  return q === SEARCH_WILDCARD || q.length >= 2 ? "" : `Enter at least 2 characters of ${what}, or * to list everyone.`;
}

/** Length of one booking slot; the grids are hourly. */
export const SLOT_DURATION_MINUTES = 60;

/**
 * An appointment stays "upcoming" until its slot has ended, so a visit that is in progress
 * (e.g. 10:01 PM for a 10 PM slot) isn't moved to past. Completed/cancelled visits never are.
 */
export function isAppointmentUpcoming(apt: { appointment_time?: string; status?: string }, now: Date = new Date()): boolean {
  if (!apt.appointment_time || apt.status === 'COMPLETED' || apt.status === 'CANCELLED') return false;
  const end = parseServerDate(apt.appointment_time).getTime() + SLOT_DURATION_MINUTES * 60_000;
  return end > now.getTime();
}

/** Key of the hourly calendar cell for `hour` on `day` in clinic time: "2026-10-22T23:00:00". */
export function cellKey(day: CalendarDay, hour: number): string {
  return `${dayKey(day)}T${pad2(hour)}:00:00`;
}

/**
 * Clinic wall-clock key ("2026-10-22T23:00:00") of the hourly calendar cell an instant falls in.
 * Booking grids are laid out in the clinic's time zone, so API timestamps are matched to cells by this key.
 */
export function clinicSlotKey(date: Date, timeZone: string): string {
  const p = zonedParts(date, timeZone);
  return cellKey(p, p.hour);
}

/** The instant a cell key ("2026-10-22T23:00:00", clinic wall-clock time) stands for. */
export function slotKeyToDate(key: string, timeZone: string): Date {
  const [datePart, timePart = '00'] = key.split('T');
  const [year, month, day] = datePart.split('-').map(Number);
  return zonedTimeToDate({ year, month, day }, Number(timePart.slice(0, 2)), timeZone);
}

export type RescheduleSlotState = 'past' | 'current' | 'available' | 'unavailable';

/**
 * State of one hourly cell in the reschedule calendar. Only future cells the doctor has AVAILABLE,
 * that aren't the appointment's current time or another booking of the same patient, can be picked.
 */
export function rescheduleSlotState(
  cell: Date,
  ctx: { now: Date; currentKey: string; statusByKey: Map<string, string>; conflictKeys: Set<string>; timeZone: string }
): RescheduleSlotState {
  const key = clinicSlotKey(cell, ctx.timeZone);
  if (cell.getTime() <= ctx.now.getTime()) return 'past';
  if (key === ctx.currentKey) return 'current';
  if (!ctx.conflictKeys.has(key) && ctx.statusByKey.get(key) === 'AVAILABLE') return 'available';
  return 'unavailable';
}

/**
 * Removes the calendar cell booked in this session for an appointment that was just cancelled.
 * `booked` holds clinic-time cell keys ("2026-10-22T23:00:00") while the API returns UTC
 * timestamps ("2026-10-23T03:00:00+00:00"), so instants are compared, not strings.
 */
export function removeCancelledBooking<T extends { slot_time: string }>(booked: T[], appointmentTime: string, timeZone: string): T[] {
  const cancelledAt = parseServerDate(appointmentTime).getTime();
  return booked.filter(entry => slotKeyToDate(entry.slot_time, timeZone).getTime() !== cancelledAt);
}
