import type { AppointmentMetrics } from "../../types/app";

/** Server-side counts from GET /admin/reports (active, non-deleted people of the whole clinic). */
export interface PeopleCounts {
  doctor_count?: number;
  patient_count?: number;
}

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
  counts: PeopleCounts | null | undefined,
  appointmentMetrics: AppointmentMetrics,
): SystemStats {
  return {
    totalDoctors: counts?.doctor_count ?? 0,
    totalPatients: counts?.patient_count ?? 0,
    totalAppointmentsToDate: appointmentMetrics.total_appointments_to_date,
    totalAppointmentsYearToDate: appointmentMetrics.total_appointments_year_to_date,
    totalAppointmentsThisMonth: appointmentMetrics.total_appointments_this_month,
    totalAppointmentsThisWeek: appointmentMetrics.total_appointments_this_week,
    totalAppointmentsToday: appointmentMetrics.total_appointments_today,
  };
}
