import { describe, expect, it } from "vitest";
import { getRouteBreadcrumb } from "./routeBreadcrumbs";
import { submenuMap } from "../config/menu";

describe("route breadcrumbs", () => {
  it("labels every support staff and new admin screen", () => {
    expect(getRouteBreadcrumb("/support/login")).toBe("Home > Support Staff > Login");
    expect(getRouteBreadcrumb("/support/patient-appointments")).toBe("Home > Support Staff > Patient Appointments");
    expect(getRouteBreadcrumb("/support/doctor-appointments")).toBe("Home > Support Staff > Doctor Appointments");
    expect(getRouteBreadcrumb("/support/doctor-availability")).toBe("Home > Support Staff > Doctor Availability");
    expect(getRouteBreadcrumb("/support/profile")).toBe("Home > Support Staff > Update Profile");
    expect(getRouteBreadcrumb("/admin/register-support-staff")).toBe("Home > Admin > Register Support Staff");
    expect(getRouteBreadcrumb("/admin/deactivate")).toBe("Home > Admin > Deactivate");
  });

  it("labels the self-service password pages", () => {
    expect(getRouteBreadcrumb("/forgot-password")).toBe("Home > Forgot Password");
    expect(getRouteBreadcrumb("/reset-password")).toBe("Home > Reset Password");
  });

  it("has a breadcrumb for every menu entry of every role", () => {
    for (const items of Object.values(submenuMap)) {
      for (const item of items) {
        expect(getRouteBreadcrumb(item.to), item.to).not.toBe("Home");
      }
    }
  });

  it("labels the doctor screens, including a consultation of any appointment", () => {
    expect(getRouteBreadcrumb("/doctors/today-appointments")).toBe("Home > Doctors > Today's Appointments");
    expect(getRouteBreadcrumb("/doctors/manage-availability")).toBe("Home > Doctors > Manage Availability");
    expect(getRouteBreadcrumb("/doctors/consultation/0b7c9d1e-1234-4abc-9def-001122334455")).toBe("Home > Doctors > Consultation");
    expect(getRouteBreadcrumb("/admin/reset-password")).toBe("Home > Admin > Reset Password / Email");
  });

  it("falls back to Home for unknown paths", () => {
    expect(getRouteBreadcrumb("/no/such/page")).toBe("Home");
  });
});
