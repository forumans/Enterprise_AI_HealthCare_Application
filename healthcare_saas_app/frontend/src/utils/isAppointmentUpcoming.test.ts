import { describe, expect, it } from "vitest";
import { isAppointmentUpcoming } from "./index";

describe("isAppointmentUpcoming", () => {
  const tenPm = "2026-10-24T02:00:00+00:00"; // 10 PM EDT on Oct 23
  const at = (iso: string) => new Date(iso);

  it("keeps an in-progress appointment upcoming until its slot ends", () => {
    expect(isAppointmentUpcoming({ appointment_time: tenPm, status: "SCHEDULED" }, at("2026-10-24T02:01:00Z"))).toBe(true);
    expect(isAppointmentUpcoming({ appointment_time: tenPm, status: "CONFIRMED" }, at("2026-10-24T02:59:00Z"))).toBe(true);
  });

  it("moves it to past once the slot has ended", () => {
    expect(isAppointmentUpcoming({ appointment_time: tenPm, status: "SCHEDULED" }, at("2026-10-24T03:00:00Z"))).toBe(false);
  });

  it("treats completed and cancelled appointments as past even before they end", () => {
    const now = at("2026-10-24T02:30:00Z");
    expect(isAppointmentUpcoming({ appointment_time: tenPm, status: "COMPLETED" }, now)).toBe(false);
    expect(isAppointmentUpcoming({ appointment_time: tenPm, status: "CANCELLED" }, now)).toBe(false);
  });

  it("handles legacy naive-UTC timestamps", () => {
    expect(isAppointmentUpcoming({ appointment_time: "2026-10-24T02:00:00", status: "SCHEDULED" }, at("2026-10-24T02:01:00Z"))).toBe(true);
  });
});
