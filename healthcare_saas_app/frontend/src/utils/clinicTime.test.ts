import { describe, expect, it } from "vitest";
import {
  addDays, cellKey, clinicSlotKey, clinicTimeNote, clinicToday, formatInZone, mondayOf, parseServerDate, slotKeyToDate,
  zonedTimeToDate,
} from "./index";

// The test runner's own zone is Asia/Tokyo (vitest.config.ts), so none of these can pass by
// accidentally using the machine's zone instead of the clinic's.
const NEW_YORK = "America/New_York";
const LOS_ANGELES = "America/Los_Angeles";
const KOLKATA = "Asia/Kolkata";

describe("clinicSlotKey", () => {
  it("keys an instant by the clinic's wall-clock hour, whatever the browser's zone", () => {
    const instant = parseServerDate("2026-10-23T03:00:00+00:00");
    expect(clinicSlotKey(instant, NEW_YORK)).toBe("2026-10-22T23:00:00");
    expect(clinicSlotKey(instant, LOS_ANGELES)).toBe("2026-10-22T20:00:00");
    expect(clinicSlotKey(instant, KOLKATA)).toBe("2026-10-23T08:00:00");
  });

  it("round-trips with slotKeyToDate", () => {
    for (const zone of [NEW_YORK, LOS_ANGELES, KOLKATA]) {
      const key = "2026-11-03T14:00:00";
      expect(clinicSlotKey(slotKeyToDate(key, zone), zone)).toBe(key);
    }
  });
});

describe("zonedTimeToDate", () => {
  it("keeps office hours fixed in local time across daylight-saving changes", () => {
    expect(zonedTimeToDate({ year: 2026, month: 10, day: 31 }, 8, NEW_YORK).toISOString()).toBe("2026-10-31T12:00:00.000Z"); // EDT
    expect(zonedTimeToDate({ year: 2026, month: 11, day: 1 }, 8, NEW_YORK).toISOString()).toBe("2026-11-01T13:00:00.000Z"); // EST
    expect(zonedTimeToDate({ year: 2026, month: 3, day: 8 }, 8, LOS_ANGELES).toISOString()).toBe("2026-03-08T15:00:00.000Z"); // PDT
  });

  it("handles zones with half-hour offsets", () => {
    expect(zonedTimeToDate({ year: 2026, month: 10, day: 22 }, 9, KOLKATA).toISOString()).toBe("2026-10-22T03:30:00.000Z");
  });
});

describe("clinic calendar days", () => {
  it("today depends on the clinic's zone at the same instant", () => {
    const instant = new Date("2026-10-22T20:00:00Z"); // 4 PM in New York, 1:30 AM next day in Kolkata
    expect(clinicToday(NEW_YORK, instant)).toEqual({ year: 2026, month: 10, day: 22 });
    expect(clinicToday(KOLKATA, instant)).toEqual({ year: 2026, month: 10, day: 23 });
  });

  it("steps across month and year ends and finds the clinic week's Monday", () => {
    expect(addDays({ year: 2026, month: 12, day: 30 }, 3)).toEqual({ year: 2027, month: 1, day: 2 });
    expect(mondayOf({ year: 2026, month: 11, day: 1 })).toEqual({ year: 2026, month: 10, day: 26 }); // Sunday
    expect(mondayOf({ year: 2026, month: 10, day: 26 })).toEqual({ year: 2026, month: 10, day: 26 }); // Monday
    expect(cellKey({ year: 2026, month: 1, day: 5 }, 8)).toBe("2026-01-05T08:00:00");
  });
});

describe("formatting in clinic time", () => {
  it("shows the clinic's wall-clock time and zone", () => {
    const text = formatInZone("2026-10-22T16:00:00+00:00", LOS_ANGELES, { hour: "numeric", minute: "2-digit", timeZoneName: "short" });
    expect(text).toBe("9:00 AM PDT");
    expect(clinicTimeNote(LOS_ANGELES, new Date("2026-10-22T16:00:00Z"))).toBe("All times are clinic time: PDT (America/Los Angeles)");
  });
});
