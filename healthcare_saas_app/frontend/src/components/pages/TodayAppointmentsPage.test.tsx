import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { TodayAppointmentsPage } from "./TodayAppointmentsPage";
import { api } from "../../api";

vi.mock("../../api", () => ({
  api: {
    getTodayAppointments: vi.fn(),
    getDoctorProfile: vi.fn(),
    confirmAppointment: vi.fn(),
    cancelAppointment: vi.fn(),
    listAllDoctorAvailability: vi.fn(),
    rescheduleAppointment: vi.fn(),
  },
}));

const auth = { session: { accessToken: "tok" } };
const later = (hours: number) => new Date(Date.now() + hours * 3_600_000).toISOString();
const appointments = [
  { id: "a1", doctor_id: "d1", time: later(1), patient_name: "Steve Works", reason: "Follow-up", status: "SCHEDULED" },
  { id: "a2", doctor_id: "d1", time: later(2), patient_name: "Paula Patient", reason: "Checkup", status: "CONFIRMED" },
];

function renderPage() {
  render(
    <MemoryRouter>
      <TodayAppointmentsPage auth={auth} userData={{}} appointments={{}} />
    </MemoryRouter>
  );
}

/** The card for a patient (the box holding their name and buttons). */
async function cardFor(name: string) {
  const heading = await screen.findByRole("heading", { name });
  return heading.closest("div[style*='border']") as HTMLElement;
}

describe("TodayAppointmentsPage", () => {
  beforeEach(() => {
    vi.mocked(api.getTodayAppointments).mockResolvedValue(appointments);
    vi.mocked(api.getDoctorProfile).mockResolvedValue({ full_name: "Dr One", phone: "5550100", specialty: "Cardiology", license_number: "L-1" });
    vi.mocked(api.cancelAppointment).mockReset();
  });

  it("offers Confirm only for scheduled visits, and Reschedule/Cancel for scheduled and confirmed ones", async () => {
    renderPage();
    const scheduled = await cardFor("Steve Works");
    const confirmed = await cardFor("Paula Patient");

    expect(within(scheduled).getByRole("button", { name: "Confirm" })).toBeInTheDocument();
    expect(within(confirmed).queryByRole("button", { name: "Confirm" })).not.toBeInTheDocument();
    for (const card of [scheduled, confirmed]) {
      expect(within(card).getByRole("button", { name: "Reschedule" })).toBeInTheDocument();
      expect(within(card).getByRole("button", { name: "Cancel" })).toBeInTheDocument();
    }
    expect(within(scheduled).getByText("Follow-up")).toBeInTheDocument(); // the visit reason is shown
  });

  it("paints Reschedule orange and Cancel red with the background shorthand (not hidden by the global button gradient)", async () => {
    renderPage();
    const card = await cardFor("Steve Works");
    expect(within(card).getByRole("button", { name: "Reschedule" }).style.background).toBe("rgb(240, 160, 32)");
    expect(within(card).getByRole("button", { name: "Cancel" }).style.background).toBe("rgb(220, 53, 69)");
  });

  it("cancels after confirmation and refreshes the list", async () => {
    renderPage();
    const card = await cardFor("Steve Works");
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.spyOn(window, "alert").mockImplementation(() => {});
    vi.mocked(api.cancelAppointment).mockResolvedValue({ message: "Appointment cancelled." });
    vi.mocked(api.getTodayAppointments).mockResolvedValue([appointments[1]]);

    await userEvent.click(within(card).getByRole("button", { name: "Cancel" }));

    expect(api.cancelAppointment).toHaveBeenCalledWith("tok", "a1");
    await screen.findByRole("heading", { name: "Paula Patient" });
    expect(screen.queryByRole("heading", { name: "Steve Works" })).not.toBeInTheDocument();
  });

  it("opens the reschedule dialog for the visit", async () => {
    vi.mocked(api.listAllDoctorAvailability).mockResolvedValue([]);
    renderPage();
    await userEvent.click(within(await cardFor("Paula Patient")).getByRole("button", { name: "Reschedule" }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Paula Patient")).toBeInTheDocument();
    expect(api.listAllDoctorAvailability).toHaveBeenCalledWith("d1", "tok");
  });
});
