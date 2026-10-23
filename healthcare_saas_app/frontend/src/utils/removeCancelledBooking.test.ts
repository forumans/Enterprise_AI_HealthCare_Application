import { describe, expect, it } from "vitest";
import { removeCancelledBooking } from "./index";

// Calendar cells are keyed by local wall-clock strings; build them from a Date so the test
// passes in any machine time zone.
const localCellString = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}T${String(d.getHours()).padStart(2, "0")}:00:00`;

describe("removeCancelledBooking", () => {
  const cancelled = new Date(Date.UTC(2026, 9, 23, 3, 0, 0)); // 11 PM on Oct 22 in New York
  const other = new Date(Date.UTC(2026, 9, 23, 13, 0, 0));
  const booked = [{ slot_time: localCellString(cancelled) }, { slot_time: localCellString(other) }];

  it("removes the cell for a cancelled appointment given as a UTC timestamp with offset", () => {
    expect(removeCancelledBooking(booked, "2026-10-23T03:00:00+00:00")).toEqual([{ slot_time: localCellString(other) }]);
  });

  it("also matches legacy naive-UTC timestamps from the API", () => {
    expect(removeCancelledBooking(booked, "2026-10-23T03:00:00")).toEqual([{ slot_time: localCellString(other) }]);
  });

  it("leaves the list unchanged when nothing matches", () => {
    expect(removeCancelledBooking(booked, "2026-10-24T03:00:00+00:00")).toEqual(booked);
  });
});
