import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AdminDeactivatePage } from "./AdminDeactivatePage";
import { api } from "../../api";
import type { AdminUserSearchRow } from "../../types";

vi.mock("../../api", () => ({
  api: { getResetPasswordRoles: vi.fn(), adminSearchUsers: vi.fn(), adminSetUserActive: vi.fn() },
}));

const auth = { session: { accessToken: "tok" } };
const ROLES = [
  { value: "PATIENT", label: "Patients" },
  { value: "DOCTOR", label: "Doctors" },
  { value: "SUPPORT_STAFF", label: "Support Staff" },
  { value: "ADMIN", label: "Admin" },
];

const row = (overrides: Partial<AdminUserSearchRow>): AdminUserSearchRow => ({
  user_id: "u", role: "ADMIN", name: "Someone", email: "x@x.test", phone: "", address: "",
  date_of_birth: "", specialty: "", is_active: true, is_self: false, ...overrides,
});

async function searchAdmins(rows: AdminUserSearchRow[]) {
  vi.mocked(api.adminSearchUsers).mockResolvedValue(rows);
  render(<AdminDeactivatePage auth={auth} />);
  await userEvent.selectOptions(await screen.findByLabelText(/Role/), "ADMIN");
  await userEvent.type(screen.getByLabelText("Search"), "*");
  await userEvent.click(screen.getByRole("button", { name: "Search" }));
  return screen.findAllByRole("row");
}

describe("AdminDeactivatePage", () => {
  beforeEach(() => {
    vi.mocked(api.getResetPasswordRoles).mockResolvedValue(ROLES);
    vi.mocked(api.adminSetUserActive).mockReset();
  });

  it("orders roles Support Staff, Doctor, Patient, Admin", async () => {
    render(<AdminDeactivatePage auth={auth} />);
    const select = await screen.findByLabelText(/Role/);
    await screen.findByRole("option", { name: "Admin" });
    expect(within(select).getAllByRole("option").map(o => o.textContent)).toEqual(["Select a role", "Support Staff", "Doctors", "Patients", "Admin"]);
  });

  it("shows a red Deactivate for active users, green Activate for deactivated ones, and no button for yourself", async () => {
    const rows = await searchAdmins([
      row({ user_id: "me", name: "Ada Admin", is_self: true }),
      row({ user_id: "a2", name: "Bob Admin" }),
      row({ user_id: "a3", name: "Cy Admin", is_active: false }),
    ]);
    expect(within(rows[0]).getAllByRole("columnheader").map(h => h.textContent)).toEqual(["#", "Full Name", "Email", "Phone", "Address", "Details", "Status", "Action"]);

    expect(within(rows[1]).getByText("Active")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Your account")).toBeInTheDocument();
    expect(within(rows[1]).queryByRole("button")).not.toBeInTheDocument();

    expect(within(rows[2]).getByRole("button", { name: "Deactivate" })).toHaveStyle({ background: "#dc3545" });
    expect(within(rows[3]).getByText("Deactivated")).toBeInTheDocument();
    expect(within(rows[3]).getByRole("button", { name: "Activate" })).toHaveStyle({ background: "#28a745" });
  });

  it("does nothing when the confirmation is cancelled", async () => {
    const rows = await searchAdmins([row({ user_id: "a2", name: "Bob Admin" })]);
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    await userEvent.click(within(rows[1]).getByRole("button", { name: "Deactivate" }));

    expect(confirm).toHaveBeenCalledWith(expect.stringContaining("Deactivate Bob Admin"));
    expect(api.adminSetUserActive).not.toHaveBeenCalled();
    expect(within(rows[1]).getByText("Active")).toBeInTheDocument();
  });

  it("deactivates after confirmation and flips the row to Activate", async () => {
    const rows = await searchAdmins([row({ user_id: "a2", name: "Bob Admin" })]);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.mocked(api.adminSetUserActive).mockResolvedValue({ message: "ok", user_id: "a2", user_email: "x", user_role: "ADMIN", is_active: false });
    await userEvent.click(within(rows[1]).getByRole("button", { name: "Deactivate" }));

    expect(api.adminSetUserActive).toHaveBeenCalledWith("tok", "a2", false);
    expect(await screen.findByText("Bob Admin has been deactivated.")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Deactivated")).toBeInTheDocument();
    expect(within(rows[1]).getByRole("button", { name: "Activate" })).toBeInTheDocument();
  });

  it("shows the server's reason when a change is refused", async () => {
    const rows = await searchAdmins([row({ user_id: "a2", name: "Bob Admin" })]);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.mocked(api.adminSetUserActive).mockRejectedValue(new Error("At least one admin must stay active."));
    await userEvent.click(within(rows[1]).getByRole("button", { name: "Deactivate" }));

    expect(await screen.findByText("At least one admin must stay active.")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Active")).toBeInTheDocument();
  });
});
