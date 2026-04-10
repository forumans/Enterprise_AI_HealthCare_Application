import type { AdminUserRow, AppointmentMetrics } from "../../types/app";

export interface SystemStats {
  totalDoctors: number;
  totalPatients: number;
  totalAppointmentsToDate: number;
  totalAppointmentsYearToDate: number;
  totalAppointmentsThisMonth: number;
  totalAppointmentsThisWeek: number;
  totalAppointmentsToday: number;
}

export const defaultAppointmentMetrics: AppointmentMetrics = {
  total_appointments_to_date: 0,
  total_appointments_year_to_date: 0,
  total_appointments_this_month: 0,
  total_appointments_this_week: 0,
  total_appointments_today: 0,
};

export function buildSystemStats(
  users: AdminUserRow[],
  appointmentMetrics: AppointmentMetrics,
): SystemStats {
  const activeUsers = users.filter(
    (user) => user.is_deleted !== true && user.deleted_at == null && user.is_active !== false,
  );

  return {
    totalDoctors: activeUsers.filter((user) => user.role === "DOCTOR").length,
    totalPatients: activeUsers.filter((user) => user.role === "PATIENT").length,
    totalAppointmentsToDate: appointmentMetrics.total_appointments_to_date,
    totalAppointmentsYearToDate: appointmentMetrics.total_appointments_year_to_date,
    totalAppointmentsThisMonth: appointmentMetrics.total_appointments_this_month,
    totalAppointmentsThisWeek: appointmentMetrics.total_appointments_this_week,
    totalAppointmentsToday: appointmentMetrics.total_appointments_today,
  };
}
