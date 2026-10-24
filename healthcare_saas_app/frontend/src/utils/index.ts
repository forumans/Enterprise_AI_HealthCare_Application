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

/**
 * Formats a date string for display
 * @param timeStr - The time string to format
 * @returns Formatted date string
 */
export function formatTime(timeStr: string): string {
  const date = parseServerDate(timeStr);
  return date.toLocaleString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

/**
 * Gets today's date in MM/DD/YYYY format
 * @returns Today's date formatted as MM/DD/YYYY
 */
export function getTodayFormatted(): string {
  const today = new Date();
  const month = String(today.getMonth() + 1).padStart(2, '0');
  const day = String(today.getDate()).padStart(2, '0');
  const year = today.getFullYear();
  return `${month}/${day}/${year}`;
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

/**
 * Local wall-clock key ("2026-10-22T23:00:00") for the hourly calendar cell an instant falls in.
 * Booking grids are laid out in the browser's time zone, so API timestamps are matched to cells by this key.
 */
export function localSlotKey(date: Date): string {
  return `${date.getFullYear().toString().padStart(4, '0')}-${(date.getMonth() + 1).toString().padStart(2, '0')}-${date.getDate().toString().padStart(2, '0')}T${date.getHours().toString().padStart(2, '0')}:00:00`;
}

export type RescheduleSlotState = 'past' | 'current' | 'available' | 'unavailable';

/**
 * State of one hourly cell in the reschedule calendar. Only future cells the doctor has AVAILABLE,
 * that aren't the appointment's current time or another booking of the same patient, can be picked.
 */
export function rescheduleSlotState(
  cell: Date,
  ctx: { now: Date; currentKey: string; statusByKey: Map<string, string>; conflictKeys: Set<string> }
): RescheduleSlotState {
  const key = localSlotKey(cell);
  if (cell.getTime() <= ctx.now.getTime()) return 'past';
  if (key === ctx.currentKey) return 'current';
  if (!ctx.conflictKeys.has(key) && ctx.statusByKey.get(key) === 'AVAILABLE') return 'available';
  return 'unavailable';
}

/**
 * Removes the calendar cell booked in this session for an appointment that was just cancelled.
 * `booked` holds local calendar-cell strings ("2026-10-22T23:00:00") while the API returns UTC
 * timestamps ("2026-10-23T03:00:00+00:00"), so instants are compared, not strings.
 */
export function removeCancelledBooking<T extends { slot_time: string }>(booked: T[], appointmentTime: string): T[] {
  const cancelledAt = parseServerDate(appointmentTime).getTime();
  return booked.filter(entry => new Date(entry.slot_time).getTime() !== cancelledAt);
}
