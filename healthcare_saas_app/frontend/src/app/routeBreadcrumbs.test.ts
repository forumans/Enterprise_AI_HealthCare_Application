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

  it("has a breadcrumb for every Support Staff menu entry", () => {
    for (const item of submenuMap["Support Staff"]) {
      expect(getRouteBreadcrumb(item.to)).not.toBe("Home");
    }
  });

  it("falls back to Home for unknown paths", () => {
    expect(getRouteBreadcrumb("/no/such/page")).toBe("Home");
  });
});
