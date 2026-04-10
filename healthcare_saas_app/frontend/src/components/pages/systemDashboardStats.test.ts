import { describe, expect, it } from "vitest";

import {
  buildSystemStats,
  defaultAppointmentMetrics,
} from "./systemDashboardStats";

describe("buildSystemStats", () => {
  it("counts only active, non-deleted doctor and patient users", () => {
    const users = [
      { id: "1", role: "DOCTOR", is_deleted: false, deleted_at: null, is_active: true },
      { id: "2", role: "DOCTOR", is_deleted: true, deleted_at: "2026-01-01", is_active: true },
      { id: "3", role: "PATIENT", is_deleted: false, deleted_at: null, is_active: true },
      { id: "4", role: "PATIENT", is_deleted: false, deleted_at: null, is_active: false },
      { id: "5", role: "ADMIN", is_deleted: false, deleted_at: null, is_active: true },
    ] as any;

    const stats = buildSystemStats(users, defaultAppointmentMetrics);

    expect(stats.totalDoctors).toBe(1);
    expect(stats.totalPatients).toBe(1);
  });

  it("maps appointment metric totals directly into dashboard stats", () => {
    const stats = buildSystemStats([], {
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
