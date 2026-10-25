import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { PatientRegistrationPage } from "./PatientRegistrationPage";
import { api } from "../../api";

vi.mock("../../api", () => ({ api: { registerPatient: vi.fn() } }));

async function fillRequiredFields() {
  await userEvent.type(screen.getByLabelText("Full Name"), "Jane Doe");
  await userEvent.type(screen.getByLabelText("Email"), "jane@example.com");
  await userEvent.type(screen.getByLabelText("Phone"), "555-123-4567");
  await userEvent.type(screen.getByLabelText("Password"), "Secret123");
}

describe("PatientRegistrationPage", () => {
  it("shows the server's reason when registration fails", async () => {
    vi.mocked(api.registerPatient).mockRejectedValue(new Error("That email is already used by another account."));
    const alert = vi.spyOn(window, "alert").mockImplementation(() => {});
    render(<MemoryRouter><PatientRegistrationPage /></MemoryRouter>);

    await fillRequiredFields();
    await userEvent.click(screen.getByRole("button", { name: "Create Account" }));

    await waitFor(() => expect(alert).toHaveBeenCalledWith("That email is already used by another account."));
    expect(screen.getByLabelText("Email")).toHaveValue("jane@example.com"); // the form keeps its input
  });

  it("sends the gender as its enum value", async () => {
    vi.mocked(api.registerPatient).mockResolvedValue({ message: "Registration successful" });
    vi.spyOn(window, "alert").mockImplementation(() => {});
    render(<MemoryRouter><PatientRegistrationPage /></MemoryRouter>);

    await fillRequiredFields();
    await userEvent.selectOptions(screen.getAllByRole("combobox")[0], "Prefer not to say");
    await userEvent.click(screen.getByRole("button", { name: "Create Account" }));

    await waitFor(() => expect(api.registerPatient).toHaveBeenCalledWith(expect.objectContaining({ gender: "PREFER_NOT_TO_SAY" })));
  });
});
