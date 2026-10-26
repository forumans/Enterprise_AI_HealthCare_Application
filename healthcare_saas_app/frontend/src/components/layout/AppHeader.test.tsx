import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AppHeader, clinicSiteUrl } from "./AppHeader";
import { api } from "../../api";
import type { SessionState } from "../../types/app";

vi.mock("../../api", () => ({ api: { getRescheduleQueue: vi.fn().mockResolvedValue([]) } }));

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

  it("shows support staff their five screens after login", async () => {
    expect(await openMenu("Support Staff", session("SUPPORT_STAFF"))).toEqual([
      "Patient Appointments", "Doctor Appointments", "Doctor Availability", "Needs Reschedule", "Update Profile",
    ]);
  });

  it("shows how many appointments need rescheduling", async () => {
    vi.mocked(api.getRescheduleQueue).mockResolvedValueOnce([{}, {}, {}] as never);
    render(
      <MemoryRouter>
        <AppHeader session={session("SUPPORT_STAFF")} onSignOut={vi.fn()} />
      </MemoryRouter>
    );
    await userEvent.click(screen.getByRole("button", { name: "Support Staff" }));
    expect(await screen.findByRole("link", { name: "Needs Reschedule (3)" })).toBeInTheDocument();
    expect(api.getRescheduleQueue).toHaveBeenCalledWith("tok");
  });

  it("does not load the queue for other roles", async () => {
    vi.mocked(api.getRescheduleQueue).mockClear();
    await openMenu("Doctors", session("DOCTOR"));
    expect(api.getRescheduleQueue).not.toHaveBeenCalled();
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

describe("AppHeader clinic name", () => {
  const renderHeader = (s: SessionState, tenantInfo: { name: string; domain?: string | null } | null) =>
    render(
      <MemoryRouter>
        <AppHeader session={s} onSignOut={vi.fn()} tenantInfo={tenantInfo} />
      </MemoryRouter>
    );

  it("links the clinic name to the clinic's own site, in a new tab", () => {
    renderHeader(session("PATIENT"), { name: "Niramaya Hospitals Group", domain: "healthylife.com" });
    const link = screen.getByRole("link", { name: "Niramaya Hospitals Group" });
    expect(link).toHaveAttribute("href", "https://healthylife.com");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(link).toHaveAttribute("title", "Niramaya Hospitals Group – healthylife.com (opens in a new tab)");
    // Sits with the brand, not floating over the menu
    expect(link.closest(".brand")).not.toBeNull();
  });

  it("shows the name without a link when the clinic has no usable domain", () => {
    for (const domain of [null, "", "javascript:alert(1)", "evil.com/path"]) {
      const { unmount } = renderHeader(session("DOCTOR"), { name: "Sunrise Clinic", domain });
      expect(screen.getByText("Sunrise Clinic").tagName).toBe("SPAN");
      expect(screen.queryByRole("link", { name: "Sunrise Clinic" })).toBeNull();
      unmount();
    }
  });

  it("shows no clinic name to signed-out visitors", () => {
    renderHeader(session("GUEST", ""), { name: "Sunrise Clinic", domain: "sunrise.example" });
    expect(screen.queryByText("Sunrise Clinic")).toBeNull();
  });
});

describe("clinicSiteUrl", () => {
  it("builds the site URL from a bare host name", () => {
    expect(clinicSiteUrl("healthylife.com")).toBe("https://healthylife.com");
    expect(clinicSiteUrl(" HealthyLife.com/ ")).toBe("https://healthylife.com");
    expect(clinicSiteUrl("https://clinic.example")).toBe("https://clinic.example");
    expect(clinicSiteUrl("localhost:5173")).toBe("http://localhost:5173");
    expect(clinicSiteUrl("default.local")).toBe("http://default.local");
  });

  it("refuses anything that isn't a host name", () => {
    for (const bad of [null, undefined, "", "javascript:alert(1)", "evil.com/path", "a b.com", "-bad.com", "x.com:99999999"]) {
      expect(clinicSiteUrl(bad)).toBeNull();
    }
  });
});
