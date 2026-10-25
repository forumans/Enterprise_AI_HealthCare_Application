import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { ConsultationForm } from "./ConsultationForm";
import { api } from "../../api";

vi.mock("../../api", () => ({
  api: {
    getAppointmentDetails: vi.fn(),
    getPharmacies: vi.fn(),
    createMedicalRecord: vi.fn(),
    getMedicalRecordByAppointment: vi.fn(),
    createPrescription: vi.fn(),
    completeAppointment: vi.fn(),
  },
}));

const session = { accessToken: "tok", role: "DOCTOR", tenantId: "t1" } as const;

async function renderForm() {
  render(<MemoryRouter><ConsultationForm session={session} appointmentId="apt-1" /></MemoryRouter>);
  await screen.findByText("Patient Consultation");
  const [symptoms, , diagnosis] = screen.getAllByRole("textbox").filter(el => el.tagName === "TEXTAREA");
  return { symptoms, diagnosis };
}

describe("ConsultationForm", () => {
  beforeEach(() => {
    vi.mocked(api.getAppointmentDetails).mockResolvedValue({
      id: "apt-1", time: "2026-10-26T16:00:00+00:00", patient_id: "p1", patient_name: "Jane Doe", status: "CONFIRMED", notes: "Checkup",
    });
    vi.mocked(api.getPharmacies).mockResolvedValue([]);
  });

  it("explains short symptoms or diagnosis instead of failing the save", async () => {
    const { symptoms, diagnosis } = await renderForm();
    const save = screen.getByRole("button", { name: "Complete Consultation" });

    await userEvent.type(symptoms, "Ache");
    await userEvent.type(diagnosis, "Flu");
    await userEvent.click(save);
    expect(screen.getByText("Symptoms must be at least 5 characters.")).toBeInTheDocument();

    await userEvent.type(symptoms, "s and fever");
    await userEvent.clear(diagnosis);
    await userEvent.type(diagnosis, "Fl");
    await userEvent.click(save);
    expect(screen.getByText("Diagnosis must be at least 3 characters.")).toBeInTheDocument();

    expect(api.createMedicalRecord).not.toHaveBeenCalled();
  });

  it("saves once both fields are long enough", async () => {
    vi.mocked(api.createMedicalRecord).mockResolvedValue({ id: "rec-1", message: "Medical record saved." });
    vi.mocked(api.completeAppointment).mockResolvedValue({ message: "Appointment status updated." });
    const { symptoms, diagnosis } = await renderForm();

    await userEvent.type(symptoms, "Fever and cough");
    await userEvent.type(diagnosis, "Flu");
    await userEvent.click(screen.getByRole("button", { name: "Complete Consultation" }));

    expect(await screen.findByText("Consultation completed successfully!")).toBeInTheDocument();
    expect(api.createMedicalRecord).toHaveBeenCalledWith(
      expect.objectContaining({ appointment_id: "apt-1", notes: "Fever and cough", diagnosis: "Flu" }), "tok",
    );
  });
});
