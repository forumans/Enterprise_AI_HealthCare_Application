import { describe, expect, it } from "vitest";
import { removeCancelledBooking } from "./index";

// Calendar cells are keyed by clinic wall-clock strings (here New York; the runner's zone is Tokyo).
const timeZone = "America/New_York";

describe("removeCancelledBooking", () => {
  const booked = [{ slot_time: "2026-10-22T23:00:00" }, { slot_time: "2026-10-23T09:00:00" }]; // 03:00Z and 13:00Z

  it("removes the cell for a cancelled appointment given as a UTC timestamp with offset", () => {
    expect(removeCancelledBooking(booked, "2026-10-23T03:00:00+00:00", timeZone)).toEqual([{ slot_time: "2026-10-23T09:00:00" }]);
  });

  it("also matches legacy naive-UTC timestamps from the API", () => {
    expect(removeCancelledBooking(booked, "2026-10-23T03:00:00", timeZone)).toEqual([{ slot_time: "2026-10-23T09:00:00" }]);
  });

  it("leaves the list unchanged when nothing matches", () => {
    expect(removeCancelledBooking(booked, "2026-10-24T03:00:00+00:00", timeZone)).toEqual(booked);
  });
});
