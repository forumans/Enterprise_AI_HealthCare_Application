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

  it("gives admins a Deactivate screen", () => {
    expect(submenuMap.Admin).toContainEqual(
      expect.objectContaining({ to: "/admin/deactivate", label: "Deactivate", requiresAuth: true, role: "ADMIN" })
    );
  });

  it("lets admins register support staff", () => {
    expect(submenuMap.Admin).toContainEqual(
      expect.objectContaining({ to: "/admin/register-support-staff", label: "Register Support Staff", role: "ADMIN" })
    );
  });
});
