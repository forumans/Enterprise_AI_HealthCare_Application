import { describe, expect, it } from "vitest";
import { localSlotKey, rescheduleSlotState } from "./index";

// Cells are built in the machine's local time, like the calendar grid, so this passes in any time zone.
const now = new Date(2026, 9, 23, 21, 30);
const cell = (hour: number, day = 24) => new Date(2026, 9, day, hour);

const ctx = (overrides: Partial<Parameters<typeof rescheduleSlotState>[1]> = {}) => ({
  now,
  currentKey: localSlotKey(cell(10)),
  statusByKey: new Map([
    [localSlotKey(cell(10)), "BOOKED"],
    [localSlotKey(cell(11)), "AVAILABLE"],
    [localSlotKey(cell(12)), "BOOKED"],
    [localSlotKey(cell(13)), "BLOCKED"],
    [localSlotKey(cell(14)), "AVAILABLE"],
    [localSlotKey(cell(21, 23)), "AVAILABLE"],
  ]),
  conflictKeys: new Set<string>(),
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
    expect(rescheduleSlotState(cell(14), ctx({ conflictKeys: new Set([localSlotKey(cell(14))]) }))).toBe("unavailable");
  });

  it("never offers a slot that has started, even if still marked available", () => {
    expect(rescheduleSlotState(cell(21, 23), ctx())).toBe("past");
  });

  it("shows an in-progress current appointment as past", () => {
    expect(rescheduleSlotState(cell(21, 23), ctx({ currentKey: localSlotKey(cell(21, 23)) }))).toBe("past");
  });
});
