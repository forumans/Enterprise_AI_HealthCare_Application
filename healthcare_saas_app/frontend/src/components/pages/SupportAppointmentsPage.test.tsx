import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SupportAppointmentsPage } from "./SupportAppointmentsPage";
import { api } from "../../api";
import { DEFAULT_CLINIC_TIMEZONE, addDays, clinicToday, zonedTimeToDate } from "../../utils";

vi.mock("../../api", () => ({
  api: {
    listDoctors: vi.fn(),
    listPatients: vi.fn(),
    supportSearchPatients: vi.fn(),
    supportSearchDoctors: vi.fn(),
    supportListAppointments: vi.fn(),
    listAllDoctorAvailability: vi.fn(),
    bookAppointment: vi.fn(),
    updateAppointmentReason: vi.fn(),
    cancelAppointment: vi.fn(),
    rescheduleAppointment: vi.fn(),
  },
}));

const auth = { session: { accessToken: "tok" } };
// Built in the clinic's zone (the default clinic zone: no provider), not the runner's (Tokyo)
const tomorrowAt = (hour: number) => zonedTimeToDate(addDays(clinicToday(DEFAULT_CLINIC_TIMEZONE), 1), hour, DEFAULT_CLINIC_TIMEZONE);
const steve = { id: "p1", name: "Steve Works", phone: "(555) 010-2030", email: "s@x.test", date_of_birth: "", gender: "", insurance_provider: "", city: "", state: "" };
const drOne = { id: "d1", name: "Dr One", phone: "555-0100", email: "doc1@x.test", specialty: "Cardiology", license_number: "L1" };
const upcoming = {
  id: "apt-1", appointment_time: tomorrowAt(9).toISOString(), status: "SCHEDULED", reason: "Knee pain review",
  patient_id: "p1", patient_name: "Steve Works", doctor_id: "d1", doctor_name: "Dr One",
};

async function pickSteve() {
  render(<SupportAppointmentsPage auth={auth} mode="patient" />);
  await userEvent.type(screen.getByLabelText("Find Patient"), "steve");
  await userEvent.click(screen.getByRole("button", { name: "Search" }));
  await userEvent.click(await screen.findByRole("button", { name: "Steve Works" }));
  return screen.findByRole("heading", { name: /Upcoming Appointments for Steve Works/ });
}

/** The table row of an appointment, found by its reason text. */
const appointmentRow = (reason: string) => screen.getByText(reason).closest("tr") as HTMLElement;

/** Records the elements scrolled into view (jsdom has no scrollIntoView). */
function trackScrolls() {
  const scrolled: Element[] = [];
  Element.prototype.scrollIntoView = vi.fn(function (this: Element) { scrolled.push(this); });
  return scrolled;
}

/** The booked appointment returned by the list reload after booking. */
const booked = { ...upcoming, id: "apt-2", appointment_time: tomorrowAt(15).toISOString(), reason: "Booked by phone call" };

/** After booking: both search result tables and the calendar are closed; only the upcoming list remains. */
function expectOnlyUpcomingListOpen() {
  const tables = screen.getAllByRole("table");
  expect(tables).toHaveLength(1);
  expect(within(tables[0]).getByText("Booked by phone call")).toBeInTheDocument();
  expect(screen.queryByText(/Booking with/)).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Book Appointment" })).not.toBeInTheDocument();
  for (const box of screen.getAllByRole("searchbox")) expect(box).toHaveValue("");
}

/** Picks tomorrow's 3 PM slot in the booking calendar (the last table), books it, and checks the request. */
async function bookTomorrowAt3() {
  vi.mocked(api.bookAppointment).mockResolvedValue({ id: "apt-2", status: "SCHEDULED" });
  vi.mocked(api.supportListAppointments).mockResolvedValue([upcoming, booked]);
  await userEvent.type(screen.getByLabelText(/Appointment Reason/), "Booked by phone call");
  // Tables: subject results, upcoming appointments, counterpart results, then the booking calendar
  await waitFor(() => expect(screen.getAllByRole("table")).toHaveLength(4));
  const calendar = screen.getAllByRole("table")[3];
  await userEvent.click(within(within(calendar).getAllByRole("cell")[1]).getByText("3:00 PM")); // tomorrow's column
  await userEvent.click(screen.getByRole("button", { name: "Book Appointment" }));

  expect(api.listAllDoctorAvailability).toHaveBeenCalledWith("d1", "tok");
  expect(api.bookAppointment).toHaveBeenCalledWith("tok", {
    doctor_id: "d1",
    patient_id: "p1",
    slot: tomorrowAt(15).toISOString(),
    reason: "Booked by phone call",
  });
  expect(window.alert).toHaveBeenCalledWith(expect.stringContaining("Appointment booked for"));
}

describe("SupportAppointmentsPage (patient mode)", () => {
  beforeEach(() => {
    vi.mocked(api.listDoctors).mockReset();
    vi.mocked(api.supportSearchPatients).mockResolvedValue([steve]);
    vi.mocked(api.supportSearchDoctors).mockResolvedValue([drOne]);
    vi.mocked(api.supportListAppointments).mockResolvedValue([upcoming]);
    vi.mocked(api.listAllDoctorAvailability).mockResolvedValue([{ slot_time: tomorrowAt(15).toISOString(), status: "AVAILABLE" }]);
    for (const fn of [api.bookAppointment, api.updateAppointmentReason, api.cancelAppointment]) vi.mocked(fn).mockReset();
    vi.spyOn(window, "alert").mockImplementation(() => {});
  });

  it("finds a patient by search and lists their upcoming appointments with actions", async () => {
    await pickSteve();
    expect(api.supportSearchPatients).toHaveBeenCalledWith("tok", "steve");
    expect(api.supportListAppointments).toHaveBeenCalledWith("tok", { patientId: "p1" });
    const row = appointmentRow("Knee pain review");
    expect(within(row).getByText("Dr One")).toBeInTheDocument();
    for (const name of ["Edit Reason", "Reschedule", "Cancel"]) {
      expect(within(row).getByRole("button", { name })).toBeInTheDocument();
    }
  });

  it("edits the reason on the patient's behalf", async () => {
    await pickSteve();
    vi.spyOn(window, "prompt").mockReturnValue("Knee and ankle pain");
    vi.mocked(api.updateAppointmentReason).mockResolvedValue({ id: "apt-1", reason: "Knee and ankle pain", status: "SCHEDULED" });
    vi.mocked(api.supportListAppointments).mockResolvedValue([{ ...upcoming, reason: "Knee and ankle pain" }]);

    await userEvent.click(within(appointmentRow("Knee pain review")).getByRole("button", { name: "Edit Reason" }));

    expect(api.updateAppointmentReason).toHaveBeenCalledWith("tok", "apt-1", "Knee and ankle pain");
    expect(await screen.findByText("Knee and ankle pain")).toBeInTheDocument();
  });

  it("rejects a too-short reason without calling the server", async () => {
    await pickSteve();
    vi.spyOn(window, "prompt").mockReturnValue("ok");
    await userEvent.click(within(appointmentRow("Knee pain review")).getByRole("button", { name: "Edit Reason" }));
    expect(window.alert).toHaveBeenCalledWith("Reason must be at least 5 characters.");
    expect(api.updateAppointmentReason).not.toHaveBeenCalled();
  });

  it("cancels after confirmation", async () => {
    await pickSteve();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.mocked(api.cancelAppointment).mockResolvedValue({ message: "Appointment cancelled." });
    vi.mocked(api.supportListAppointments).mockResolvedValue([]);

    await userEvent.click(within(appointmentRow("Knee pain review")).getByRole("button", { name: "Cancel" }));

    expect(api.cancelAppointment).toHaveBeenCalledWith("tok", "apt-1");
    expect(await screen.findByText("No upcoming appointments")).toBeInTheDocument();
  });

  it("scrolls down to the patient's appointments once a patient is picked", async () => {
    const scrolled = trackScrolls();
    const heading = await pickSteve();
    await waitFor(() => expect(scrolled).toContain(heading.closest(".card")));
  });

  it("searches for the doctor, books, then scrolls up to the new appointment", async () => {
    const scrolled = trackScrolls();
    await pickSteve();
    expect(api.listDoctors).not.toHaveBeenCalled();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();

    // Doctor search inside the booking card
    await userEvent.type(screen.getByLabelText("Find Doctor"), "doc1@");
    await userEvent.click(screen.getAllByRole("button", { name: "Search" })[1]);
    await userEvent.click(await screen.findByRole("button", { name: "Dr One" }));
    expect(api.supportSearchDoctors).toHaveBeenCalledWith("tok", "doc1@");
    const bookingWith = await screen.findByText(/Booking with doctor:/);
    await waitFor(() => expect(scrolled).toContain(bookingWith.parentElement));

    await bookTomorrowAt3();
    await waitFor(() => expect(scrolled[scrolled.length - 1]).toBe(appointmentRow("Booked by phone call")));
    expectOnlyUpcomingListOpen();
  });
});

describe("SupportAppointmentsPage (doctor mode)", () => {
  beforeEach(() => {
    vi.mocked(api.supportSearchDoctors).mockResolvedValue([drOne]);
    vi.mocked(api.supportSearchPatients).mockResolvedValue([steve]);
    vi.mocked(api.supportListAppointments).mockResolvedValue([upcoming]);
    vi.mocked(api.listAllDoctorAvailability).mockResolvedValue([{ slot_time: tomorrowAt(15).toISOString(), status: "AVAILABLE" }]);
    vi.mocked(api.bookAppointment).mockReset();
    vi.mocked(api.listPatients).mockReset();
    vi.spyOn(window, "alert").mockImplementation(() => {});
  });

  it("searches for the patient, books with the doctor, then scrolls up to the new appointment", async () => {
    const scrolled = trackScrolls();
    render(<SupportAppointmentsPage auth={auth} mode="doctor" />);
    await userEvent.type(screen.getByLabelText("Find Doctor"), "one");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));
    await userEvent.click(await screen.findByRole("button", { name: "Dr One" }));
    const heading = await screen.findByRole("heading", { name: /Upcoming Appointments for Dr One/ });
    await waitFor(() => expect(scrolled).toContain(heading.closest(".card")));
    expect(api.listPatients).not.toHaveBeenCalled();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();

    // Patient search inside the booking card: email works as a search term
    await userEvent.type(screen.getByLabelText("Find Patient"), "s@x.test");
    await userEvent.click(screen.getAllByRole("button", { name: "Search" })[1]);
    await userEvent.click(await screen.findByRole("button", { name: "Steve Works" }));
    expect(api.supportSearchPatients).toHaveBeenCalledWith("tok", "s@x.test");
    const bookingWith = await screen.findByText(/Booking with patient:/);
    await waitFor(() => expect(scrolled).toContain(bookingWith.parentElement));

    await bookTomorrowAt3();
    await waitFor(() => expect(scrolled[scrolled.length - 1]).toBe(appointmentRow("Booked by phone call")));
    expectOnlyUpcomingListOpen();
  });
});
