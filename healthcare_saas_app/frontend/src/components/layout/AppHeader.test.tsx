import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AppHeader } from "./AppHeader";
import type { SessionState } from "../../types/app";

const session = (role: SessionState["role"], accessToken = "tok") => ({ accessToken, role, tenantId: "t" }) as SessionState;

async function openMenu(name: string, s: SessionState) {
  render(
    <MemoryRouter>
      <AppHeader session={s} onSignOut={vi.fn()} />
    </MemoryRouter>
  );
  await userEvent.click(screen.getByRole("button", { name }));
  const dropdown = document.querySelector(".floating-dropdown") as HTMLElement;
  return within(dropdown).queryAllByRole("link").map(link => link.textContent);
}

describe("AppHeader menus", () => {
  it("has a Support Staff menu between Patients and Admin", () => {
    render(
      <MemoryRouter>
        <AppHeader session={session("GUEST", "")} onSignOut={vi.fn()} />
      </MemoryRouter>
    );
    const nav = screen.getByRole("navigation");
    expect(within(nav).getAllByRole("button").map(b => b.textContent)).toEqual(["Home", "Doctors", "Patients", "Support Staff", "Admin"]);
  });

  it("offers only Login to guests in the Support Staff menu", async () => {
    expect(await openMenu("Support Staff", session("GUEST", ""))).toEqual(["Login"]);
  });

  it("shows support staff their four screens after login", async () => {
    expect(await openMenu("Support Staff", session("SUPPORT_STAFF"))).toEqual([
      "Patient Appointments", "Doctor Appointments", "Doctor Availability", "Update Profile",
    ]);
  });

  it("does not show support staff screens to other roles", async () => {
    expect(await openMenu("Support Staff", session("DOCTOR"))).toEqual([]);
  });

  it("lists admin screens with System Dashboard first and the new account tools", async () => {
    expect(await openMenu("Admin", session("ADMIN"))).toEqual([
      "System Dashboard", "Register Doctor", "Register Patient", "Register Admin", "Register Support Staff", "Reset Password / Email", "Deactivate", "Clinic Settings",
    ]);
  });
});
