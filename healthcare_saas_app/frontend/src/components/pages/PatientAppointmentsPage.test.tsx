import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PatientAppointmentsPage } from "./PatientAppointmentsPage";
import { ClinicTimeZoneContext } from "../../contexts/ClinicTimeZoneContext";
import { api } from "../../api";

vi.mock("../../api", () => ({
  api: { listDoctors: vi.fn(), listAllDoctorAvailability: vi.fn(), listAllAppointments: vi.fn(), bookAppointment: vi.fn(), cancelAppointment: vi.fn() },
}));

const CLINIC_ZONE = "America/Los_Angeles";

describe("PatientAppointmentsPage", () => {
  beforeEach(() => {
    // Sunday Oct 25, 2026, 11:35 AM in the clinic (Los Angeles)
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-10-25T18:35:00Z"));
    vi.mocked(api.listDoctors).mockResolvedValue([{ id: "doc-1", name: "Dr One", specialty: "Cardiology" }]);
    vi.mocked(api.listAllDoctorAvailability).mockResolvedValue([
      { slot_time: "2026-10-26T21:00:00+00:00", status: "BOOKED" },     // Mon 2 PM, the patient's own visit
      { slot_time: "2026-10-26T22:00:00+00:00", status: "AVAILABLE" },  // Mon 3 PM
    ]);
  });
  afterEach(() => vi.useRealTimers());

  it("uses one appointment list for the tables and the calendar (no second fetch)", async () => {
    const appointments = {
      appointments: [{ id: "a1", doctor_id: "doc-1", doctor_name: "Dr One", appointment_time: "2026-10-26T21:00:00+00:00", status: "SCHEDULED", notes: "Checkup" }],
      loadPatientAppointments: vi.fn().mockResolvedValue(undefined),
    };
    const userData = { loadPatientDetails: vi.fn().mockResolvedValue(undefined), patientDetails: null };
    render(
      <ClinicTimeZoneContext.Provider value={CLINIC_ZONE}>
        <PatientAppointmentsPage auth={{ session: { accessToken: "tok" } }} appointments={appointments} userData={userData} />
      </ClinicTimeZoneContext.Provider>
    );

    await userEvent.selectOptions(await screen.findByRole("combobox"), "doc-1");
    await waitFor(() => expect(api.listAllDoctorAvailability).toHaveBeenCalledWith("doc-1", "tok"));

    const monday = within(screen.getAllByRole("table")[0]).getAllByRole("cell")[1];
    await waitFor(() => expect(within(monday).getByText("3:00 PM")).toHaveStyle({ backgroundColor: "#28a745" }));
    expect(within(monday).getByText("2:00 PM")).toHaveStyle({ backgroundColor: "#dc3545" });  // the patient's own booking
    expect(screen.getByText("Upcoming (1)")).toBeInTheDocument();
    expect(api.listAllAppointments).not.toHaveBeenCalled();  // the hook loads the list; the page doesn't fetch it again
  });

  it("lists cancelled visits under Past, marked CANCELLED, and doesn't treat their time as taken", async () => {
    const appointments = {
      appointments: [
        { id: "a2", doctor_id: "doc-1", doctor_name: "Dr One", appointment_time: "2026-10-26T22:00:00+00:00", status: "CANCELLED", notes: "Follow-up" },
      ],
      loadPatientAppointments: vi.fn().mockResolvedValue(undefined),
    };
    const userData = { loadPatientDetails: vi.fn().mockResolvedValue(undefined), patientDetails: null };
    render(
      <ClinicTimeZoneContext.Provider value={CLINIC_ZONE}>
        <PatientAppointmentsPage auth={{ session: { accessToken: "tok" } }} appointments={appointments} userData={userData} />
      </ClinicTimeZoneContext.Provider>
    );

    expect(await screen.findByText("Upcoming (0)")).toBeInTheDocument();
    const pastTable = screen.getByText("Past (1)").nextElementSibling as HTMLElement;
    const status = within(pastTable).getByText("CANCELLED");
    expect(status).toHaveStyle({ color: "#ff90ab" });
    expect(within(pastTable).queryByRole("button", { name: "Cancel" })).toBeNull();

    // The cancelled 3 PM slot is open again in the calendar
    await userEvent.selectOptions(screen.getByRole("combobox"), "doc-1");
    const monday = within(screen.getAllByRole("table")[0]).getAllByRole("cell")[1];
    await waitFor(() => expect(within(monday).getByText("3:00 PM")).toHaveStyle({ backgroundColor: "#28a745" }));
  });
});
