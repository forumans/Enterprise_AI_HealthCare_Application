import type { View } from "./types";

const viewBreadcrumbMap: Record<View, string> = {
  home: "Home",
  login: "Home > Login",
  register: "Home > Patient > Register",
  password: "Home > Forgot / Reset Password",
  "patient-schedule": "Home > Patients > Schedule / Cancel Appointment",
  "patient-prescriptions": "Home > Patients > Prescriptions",
  "patient-bill-pay": "Home > Patients > Bill Pay",
  doctor: "Home > Doctors > Appointments",
  "doctor-search": "Home > Doctors > Search Patients",
  "doctor-slots": "Home > Doctors > Update Available Slots",
  admin: "Home > Admin",
};

export function getBreadcrumb(view: View): string {
  return viewBreadcrumbMap[view] ?? "Home";
}
