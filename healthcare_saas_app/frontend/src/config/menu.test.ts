import { describe, expect, it } from "vitest";
import { getMainMenuFromPath, submenuMap } from "./menu";

describe("Support Staff menu", () => {
  it("maps /support routes to the Support Staff menu", () => {
    expect(getMainMenuFromPath("/support/patient-appointments")).toBe("Support Staff");
    expect(getMainMenuFromPath("/support/login")).toBe("Support Staff");
    expect(getMainMenuFromPath("/admin/register-support-staff")).toBe("Admin");
  });

  it("offers login to guests and the management and profile screens to support staff only", () => {
    const items = submenuMap["Support Staff"];
    expect(items.filter(i => i.hideWhenAuth).map(i => i.to)).toEqual(["/support/login"]);
    expect(items.filter(i => i.requiresAuth).map(i => [i.to, i.role])).toEqual([
      ["/support/patient-appointments", "SUPPORT_STAFF"],
      ["/support/doctor-appointments", "SUPPORT_STAFF"],
      ["/support/doctor-availability", "SUPPORT_STAFF"],
      ["/support/profile", "SUPPORT_STAFF"],
    ]);
  });

  it("lists System Dashboard first in the Admin menu after login", () => {
    const afterLogin = submenuMap.Admin.filter(i => !i.hideWhenAuth);
    expect(afterLogin[0]).toEqual(expect.objectContaining({ to: "/admin/system-dashboard", label: "System Dashboard" }));
    expect(afterLogin.map(i => i.label)).toContain("Reset Password / Email");
  });

  it("gives admins a Deactivate screen", () => {
    expect(submenuMap.Admin).toContainEqual(
      expect.objectContaining({ to: "/admin/deactivate", label: "Deactivate", requiresAuth: true, role: "ADMIN" })
    );
  });

  it("gives admins a Clinic Settings screen (time zone)", () => {
    expect(submenuMap.Admin).toContainEqual(
      expect.objectContaining({ to: "/admin/clinic-settings", label: "Clinic Settings", requiresAuth: true, role: "ADMIN" })
    );
  });

  it("lets admins register support staff", () => {
    expect(submenuMap.Admin).toContainEqual(
      expect.objectContaining({ to: "/admin/register-support-staff", label: "Register Support Staff", role: "ADMIN" })
    );
  });
});
