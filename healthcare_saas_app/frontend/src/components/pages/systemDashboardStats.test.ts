import { describe, expect, it } from "vitest";

import {
  buildSystemStats,
  defaultAppointmentMetrics,
} from "./systemDashboardStats";

describe("buildSystemStats", () => {
  it("uses the server-side doctor and patient counts (not a paged user list)", () => {
    const stats = buildSystemStats({ doctor_count: 42, patient_count: 1250 }, defaultAppointmentMetrics);

    expect(stats.totalDoctors).toBe(42);
    expect(stats.totalPatients).toBe(1250);
  });

  it("shows zero when the counts haven't loaded", () => {
    const stats = buildSystemStats(null, defaultAppointmentMetrics);

    expect(stats.totalDoctors).toBe(0);
    expect(stats.totalPatients).toBe(0);
  });

  it("maps appointment metric totals directly into dashboard stats", () => {
    const stats = buildSystemStats({}, {
      total_appointments_to_date: 100,
      total_appointments_year_to_date: 80,
      total_appointments_this_month: 20,
      total_appointments_this_week: 5,
      total_appointments_today: 1,
    });

    expect(stats.totalAppointmentsToDate).toBe(100);
    expect(stats.totalAppointmentsYearToDate).toBe(80);
    expect(stats.totalAppointmentsThisMonth).toBe(20);
    expect(stats.totalAppointmentsThisWeek).toBe(5);
    expect(stats.totalAppointmentsToday).toBe(1);
  });
});
