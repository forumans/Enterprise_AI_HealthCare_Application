import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { PatientProfilePage } from "./PatientProfilePage";
import { api } from "../../api";

vi.mock("../../api", () => ({ api: { getPatientProfile: vi.fn(), updatePatientProfile: vi.fn() } }));

describe("PatientProfilePage", () => {
  it("sends an emptied optional field as an empty value, so the stored value is cleared", async () => {
    vi.mocked(api.getPatientProfile).mockResolvedValue({
      full_name: "Jane Doe", phone: "555-123-4567", date_of_birth: "1985-03-07", gender: "FEMALE",
      address_line1: "1 Main St", address_line2: "", city: "Austin", state: "TX", postal_code: "73301",
      country: "United States", insurance_provider: "Acme", insurance_policy_number: "P-1",
    });
    vi.mocked(api.updatePatientProfile).mockResolvedValue({ message: "Profile updated successfully" });
    const userData = { loadPatientDetails: vi.fn() };
    render(<MemoryRouter><PatientProfilePage auth={{ session: { accessToken: "tok" } }} userData={userData} /></MemoryRouter>);

    const city = screen.getByLabelText("City");
    await waitFor(() => expect(city).toHaveValue("Austin"));
    await userEvent.clear(city);
    await userEvent.clear(screen.getByLabelText("Insurance Provider"));
    await userEvent.click(screen.getByRole("button", { name: "Update Profile" }));

    await waitFor(() => expect(api.updatePatientProfile).toHaveBeenCalled());
    const payload = vi.mocked(api.updatePatientProfile).mock.calls[0][1];
    expect(payload).toMatchObject({ city: "", insuranceProvider: "", state: "TX", fullName: "Jane Doe", gender: "FEMALE" });
  });
});
