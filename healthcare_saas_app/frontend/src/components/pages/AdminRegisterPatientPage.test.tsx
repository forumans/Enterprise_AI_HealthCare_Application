import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AdminRegisterPatientPage } from "./AdminRegisterPatientPage";
import { api } from "../../api";

vi.mock("../../api", () => ({ api: { registerPatientAdmin: vi.fn() } }));

const auth = { session: { accessToken: "tok", role: "ADMIN" } };

describe("AdminRegisterPatientPage", () => {
  it("offers the gender enum values, so admin-created patients store MALE/FEMALE/...", async () => {
    vi.mocked(api.registerPatientAdmin).mockResolvedValue({ message: "Patient registration successful!" });
    render(<MemoryRouter><AdminRegisterPatientPage auth={auth} /></MemoryRouter>);

    const gender = screen.getByRole("combobox");
    expect([...gender.querySelectorAll("option")].map(o => o.value)).toEqual(["", "MALE", "FEMALE", "OTHER", "PREFER_NOT_TO_SAY"]);

    await userEvent.type(screen.getByLabelText("Full Name"), "Pat New");
    await userEvent.type(screen.getByLabelText("Email"), "pat@example.com");
    await userEvent.type(screen.getByLabelText("Phone"), "555-123-4567");
    await userEvent.type(screen.getByLabelText("Password"), "Secret123");
    await userEvent.type(screen.getByLabelText("Date of Birth"), "1990-05-01");
    await userEvent.selectOptions(gender, "Female");
    await userEvent.click(screen.getByRole("button", { name: /register patient/i }));

    await waitFor(() => expect(api.registerPatientAdmin).toHaveBeenCalledWith(expect.objectContaining({ gender: "FEMALE" }), "tok"));
  });
});
