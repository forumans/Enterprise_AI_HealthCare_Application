/**
 * Menu configuration and navigation structure
 * This module defines the navigation menu structure for different user roles
 */

import type { MainMenu, SubmenuItem, SubmenuMap } from "../types/app";

export const submenuMap: SubmenuMap = {
  Home: [],
  Doctors: [
    { to: "/doctors/login", label: "Login", hideWhenAuth: true },
    { to: "/doctors/register", label: "Register", hideWhenAuth: true },
    { to: "/doctors/appointments", label: "Weekly Appointments", requiresAuth: true, role: "DOCTOR" },
    { to: "/doctors/today-appointments", label: "Today's Appointments", requiresAuth: true, role: "DOCTOR" },
    { to: "/doctors/search-patients", label: "Search Patients", requiresAuth: true, role: "DOCTOR" },
    { to: "/doctors/manage-availability", label: "Manage Availability", requiresAuth: true, role: "DOCTOR" },
    { to: "/doctors/profile", label: "Update Profile", requiresAuth: true, role: "DOCTOR" },
  ],
  Patients: [
    { to: "/patients/login", label: "Login", hideWhenAuth: true },
    { to: "/patients/register", label: "Register", hideWhenAuth: true },
    { to: "/patients/appointments", label: "Schedule Appointment", requiresAuth: true, role: "PATIENT" },
    { to: "/patients/prescriptions", label: "Prescriptions", requiresAuth: true, role: "PATIENT" },
    { to: "/patients/billing", label: "Billing", requiresAuth: true, role: "PATIENT" },
    { to: "/patients/profile", label: "Update Profile", requiresAuth: true, role: "PATIENT" },
  ],
  "Support Staff": [
    { to: "/support/login", label: "Login", hideWhenAuth: true },
    { to: "/support/patient-appointments", label: "Patient Appointments", requiresAuth: true, role: "SUPPORT_STAFF" },
    { to: "/support/doctor-appointments", label: "Doctor Appointments", requiresAuth: true, role: "SUPPORT_STAFF" },
    { to: "/support/doctor-availability", label: "Doctor Availability", requiresAuth: true, role: "SUPPORT_STAFF" },
    { to: "/support/needs-reschedule", label: "Needs Reschedule", requiresAuth: true, role: "SUPPORT_STAFF", badge: "rescheduleQueue" },
    { to: "/support/profile", label: "Update Profile", requiresAuth: true, role: "SUPPORT_STAFF" },
  ],
  Admin: [
    { to: "/admin/login", label: "Login Admin", hideWhenAuth: true },
    { to: "/admin/system-dashboard", label: "System Dashboard", requiresAuth: true, role: "ADMIN" },
    { to: "/admin/register-doctor", label: "Register Doctor", requiresAuth: true, role: "ADMIN" },
    { to: "/admin/register-patient", label: "Register Patient", requiresAuth: true, role: "ADMIN" },
    { to: "/admin/register-admin", label: "Register Admin", requiresAuth: true, role: "ADMIN" },
    { to: "/admin/register-support-staff", label: "Register Support Staff", requiresAuth: true, role: "ADMIN" },
    { to: "/admin/reset-password", label: "Reset Password / Email", requiresAuth: true, role: "ADMIN" },
    { to: "/admin/deactivate", label: "Deactivate", requiresAuth: true, role: "ADMIN" },
    { to: "/admin/clinic-settings", label: "Clinic Settings", requiresAuth: true, role: "ADMIN" },
  ],
};

/** A menu item's label with its count badge when the count is above zero: "Needs Reschedule (3)". */
export function menuItemLabel(item: SubmenuItem, counts: Partial<Record<NonNullable<SubmenuItem["badge"]>, number>>): string {
  const count = item.badge ? counts[item.badge] ?? 0 : 0;
  return count > 0 ? `${item.label} (${count})` : item.label;
}

/**
 * Determines the main menu based on the current pathname
 * @param pathname - The current URL pathname
 * @returns The corresponding MainMenu type
 */
export function getMainMenuFromPath(pathname: string): MainMenu {
  if (pathname.startsWith("/doctors")) {
    return "Doctors";
  }
  if (pathname.startsWith("/patients")) {
    return "Patients";
  }
  if (pathname.startsWith("/support")) {
    return "Support Staff";
  }
  if (pathname.startsWith("/admin")) {
    return "Admin";
  }
  return "Home";
}
