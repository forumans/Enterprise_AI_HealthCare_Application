import { describe, expect, it } from "vitest";
import { clinicSlotKey, rescheduleSlotState, zonedTimeToDate } from "./index";

// Cells are built in the clinic's zone, like the calendar grid; the runner's own zone differs (Tokyo).
const timeZone = "America/Los_Angeles";
const now = zonedTimeToDate({ year: 2026, month: 10, day: 23 }, 21, timeZone);
const nowPlusHalfHour = new Date(now.getTime() + 30 * 60_000);
const cell = (hour: number, day = 24) => zonedTimeToDate({ year: 2026, month: 10, day }, hour, timeZone);
const key = (hour: number, day = 24) => clinicSlotKey(cell(hour, day), timeZone);

const ctx = (overrides: Partial<Parameters<typeof rescheduleSlotState>[1]> = {}) => ({
  now: nowPlusHalfHour,
  currentKey: key(10),
  statusByKey: new Map([
    [key(10), "BOOKED"],
    [key(11), "AVAILABLE"],
    [key(12), "BOOKED"],
    [key(13), "BLOCKED"],
    [key(14), "AVAILABLE"],
    [key(21, 23), "AVAILABLE"],
  ]),
  conflictKeys: new Set<string>(),
  timeZone,
  ...overrides,
});

describe("rescheduleSlotState", () => {
  it("offers future slots the doctor has available", () => {
    expect(rescheduleSlotState(cell(11), ctx())).toBe("available");
  });

  it("marks the appointment's own time as current, not selectable", () => {
    expect(rescheduleSlotState(cell(10), ctx())).toBe("current");
  });

  it("treats booked, blocked and missing slots as unavailable", () => {
    expect(rescheduleSlotState(cell(12), ctx())).toBe("unavailable");
    expect(rescheduleSlotState(cell(13), ctx())).toBe("unavailable");
    expect(rescheduleSlotState(cell(15), ctx())).toBe("unavailable");
  });

  it("blocks times where the patient already has another appointment", () => {
    expect(rescheduleSlotState(cell(14), ctx({ conflictKeys: new Set([key(14)]) }))).toBe("unavailable");
  });

  it("never offers a slot that has started, even if still marked available", () => {
    expect(rescheduleSlotState(cell(21, 23), ctx())).toBe("past");
  });

  it("shows an in-progress current appointment as past", () => {
    expect(rescheduleSlotState(cell(21, 23), ctx({ currentKey: key(21, 23) }))).toBe("past");
  });
});
