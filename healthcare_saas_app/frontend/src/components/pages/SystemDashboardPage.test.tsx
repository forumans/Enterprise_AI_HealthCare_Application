import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { SystemDashboardPage } from "./SystemDashboardPage";

const users = [
  { id: "u1", name: "Ada Admin", email: "ada@x.test", role: "ADMIN", is_deleted: false, is_active: true },
  { id: "u2", name: "Dr Pending", email: "doc@x.test", role: "DOCTOR", is_deleted: false, is_active: false },
];

function renderDashboard() {
  const userData = {
    tenantInfo: { name: "Sunrise Clinic" },
    adminUsers: users,
    reports: {},
    appointmentMetrics: {},
    loadAdminDashboard: vi.fn().mockResolvedValue({ adminUsers: users, reports: { doctor_count: 1, patient_count: 2 }, appointmentMetrics: undefined }),
  };
  const auth = { session: { accessToken: "tok", role: "ADMIN", userName: "Ada Admin" } };
  render(<MemoryRouter><SystemDashboardPage auth={auth} userData={userData} /></MemoryRouter>);
}

describe("SystemDashboardPage", () => {
  it("shows the signed-in admin's name and the clinic", async () => {
    renderDashboard();
    const card = screen.getByRole("heading", { name: "Administrator" }).parentElement as HTMLElement;
    expect(within(card).getByText("Ada Admin")).toBeInTheDocument();
    expect(within(card).getByText("Sunrise Clinic")).toBeInTheDocument();
  });

  it("labels recent users Active or Inactive from their account status", async () => {
    renderDashboard();
    const rows = (await screen.findAllByRole("row")).slice(1);
    expect(within(rows[0]).getByText("Active")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Inactive")).toBeInTheDocument();
  });
});
