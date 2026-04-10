export const menuToViewMap: Record<string, string> = {
  Home: "home",
  Login: "login",
  Register: "register",
  Password: "password",
  "Schedule / Cancel Appointment": "patient-schedule",
  Prescriptions: "patient-prescriptions",
  "Bill Pay": "patient-bill-pay",
  Appointments: "doctor",
  "Search Patients": "doctor-search",
  "Update Available Slots": "doctor-slots",
  "Register Doctor": "admin",
  "Register Patient": "admin",
  "Register Admin": "admin",
};

export function menuToView(value: string): string {
  return menuToViewMap[value] ?? "home";
}

export function breadcrumb(parts: string[]): string {
  return parts.join(" > ");
}
