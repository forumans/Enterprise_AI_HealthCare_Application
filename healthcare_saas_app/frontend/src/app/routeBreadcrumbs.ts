const routeLabelMap: Array<{ test: (path: string) => boolean; label: string }> = [
  { test: (path) => path === "/", label: "Home" },
  { test: (path) => path === "/patients/login", label: "Home > Patients > Login" },
  { test: (path) => path === "/patients/register", label: "Home > Patients > Register" },
  { test: (path) => path === "/patients/appointments", label: "Home > Patients > Schedule Appointment" },
  { test: (path) => path === "/patients/prescriptions", label: "Home > Patients > Prescriptions" },
  { test: (path) => path === "/patients/billing", label: "Home > Patients > Billing" },
  { test: (path) => path === "/doctors/login", label: "Home > Doctors > Login" },
  { test: (path) => path === "/doctors/register", label: "Home > Doctors > Register" },
  { test: (path) => path === "/doctors/appointments", label: "Home > Doctors > Appointments" },
  { test: (path) => path === "/doctors/search-patients", label: "Home > Doctors > Search Patients" },
  { test: (path) => path === "/doctors/availability", label: "Home > Doctors > Availability Slots" },
  { test: (path) => path === "/admin/register-doctor", label: "Home > Admin > Register Doctor" },
  { test: (path) => path === "/admin/register-patient", label: "Home > Admin > Register Patient" },
  { test: (path) => path === "/admin/register-admin", label: "Home > Admin > Register Admin" },
  { test: (path) => path === "/admin/system-dashboard", label: "Home > Admin > System Dashboard" },
  { test: (path) => path === "/more/password", label: "Home > More > Password" },
  { test: (path) => path === "/more/profile", label: "Home > More > Profile" },
];

export function getRouteBreadcrumb(pathname: string): string {
  const hit = routeLabelMap.find((entry) => entry.test(pathname));
  return hit?.label ?? "Home";
}
