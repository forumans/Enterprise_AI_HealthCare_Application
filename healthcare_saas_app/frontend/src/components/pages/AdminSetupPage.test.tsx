import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AdminSetupPage } from "./AdminSetupPage";
import { api } from "../../api";

vi.mock("../../api", () => ({ api: { getAdminSetupStatus: vi.fn(), bootstrapAdmin: vi.fn() } }));

const renderPage = () => render(<MemoryRouter><AdminSetupPage /></MemoryRouter>);

describe("AdminSetupPage", () => {
  beforeEach(() => vi.mocked(api.bootstrapAdmin).mockReset());

  it("creates the first administrator when setup is required", async () => {
    vi.mocked(api.getAdminSetupStatus).mockResolvedValue({ setup_required: true });
    vi.mocked(api.bootstrapAdmin).mockResolvedValue({ message: "Admin registration successful for Ada Admin" });
    renderPage();

    await userEvent.type(await screen.findByLabelText(/Full Name/, { selector: "input" }), "Ada Admin");
    await userEvent.type(screen.getByLabelText(/^Email/, { selector: "input" }), "ada@clinic.test");
    await userEvent.type(screen.getByLabelText(/^Password/, { selector: "input" }), "Str0ngPass");
    await userEvent.type(screen.getByLabelText(/Confirm Password/, { selector: "input" }), "Str0ngPass");
    // The clinic zone starts as the browser's (Tokyo in tests) and can be changed
    expect(screen.getByLabelText("Clinic Time Zone")).toHaveValue("Asia/Tokyo");
    await userEvent.selectOptions(screen.getByLabelText("Clinic Time Zone"), "America/Chicago");
    await userEvent.click(screen.getByRole("button", { name: "Create Administrator" }));

    expect(api.bootstrapAdmin).toHaveBeenCalledWith({ full_name: "Ada Admin", email: "ada@clinic.test", password: "Str0ngPass", timezone: "America/Chicago" });
    expect(await screen.findByText("Admin registration successful for Ada Admin")).toBeInTheDocument();
  });

  it("rejects a password shorter than 8 characters without calling the server", async () => {
    vi.mocked(api.getAdminSetupStatus).mockResolvedValue({ setup_required: true });
    renderPage();

    await userEvent.type(await screen.findByLabelText(/Full Name/, { selector: "input" }), "Ada Admin");
    await userEvent.type(screen.getByLabelText(/^Email/, { selector: "input" }), "ada@clinic.test");
    await userEvent.type(screen.getByLabelText(/^Password/, { selector: "input" }), "short1");
    await userEvent.type(screen.getByLabelText(/Confirm Password/, { selector: "input" }), "short1");
    await userEvent.click(screen.getByRole("button", { name: "Create Administrator" }));

    expect(screen.getByText("Password must be at least 8 characters long.")).toBeInTheDocument();
    expect(api.bootstrapAdmin).not.toHaveBeenCalled();
  });

  it("shows no form once the system is set up", async () => {
    vi.mocked(api.getAdminSetupStatus).mockResolvedValue({ setup_required: false });
    renderPage();

    expect(await screen.findByText(/already set up/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Create Administrator" })).not.toBeInTheDocument();
  });
});
