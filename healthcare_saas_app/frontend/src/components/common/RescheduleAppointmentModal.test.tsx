import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RescheduleAppointmentModal } from "./RescheduleAppointmentModal";
import { api } from "../../api";

vi.mock("../../api", () => ({
  api: { listAllDoctorAvailability: vi.fn(), rescheduleAppointment: vi.fn() },
}));

// Slots are built in the machine's local time, like the calendar grid, for tomorrow (always in the first week shown)
const now = new Date();
const tomorrowAt = (hour: number) => new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1, hour);
const iso = (hour: number) => tomorrowAt(hour).toISOString();

const target = {
  id: "apt-1",
  doctorId: "doc-1",
  appointmentTime: iso(10),
  doctorName: "Dr One",
  patientName: "Steve Works",
  reason: "Knee pain review",
  status: "CONFIRMED",
};

/** The calendar column for tomorrow (the grid starts today). */
async function tomorrowColumn() {
  const table = await screen.findByRole("table");
  return within(table).getAllByRole("cell")[1];
}

describe("RescheduleAppointmentModal", () => {
  beforeEach(() => {
    vi.mocked(api.listAllDoctorAvailability).mockResolvedValue([
      { slot_time: iso(10), status: "BOOKED" },
      { slot_time: iso(11), status: "AVAILABLE" },
      { slot_time: iso(12), status: "BLOCKED" },
      { slot_time: iso(13), status: "AVAILABLE" },
    ]);
    vi.mocked(api.rescheduleAppointment).mockReset();
  });

  it("shows the appointment details that stay the same", async () => {
    render(<RescheduleAppointmentModal target={target} accessToken="tok" onClose={vi.fn()} onRescheduled={vi.fn()} />);
    const dialog = screen.getByRole("dialog");
    for (const text of ["Steve Works", "Dr One", "CONFIRMED", "Knee pain review"]) {
      expect(within(dialog).getByText(text)).toBeInTheDocument();
    }
    expect(api.listAllDoctorAvailability).toHaveBeenCalledWith("doc-1", "tok");
    expect(screen.getByRole("button", { name: "Confirm Reschedule" })).toBeDisabled();
  });

  it("only lets open future slots be picked", async () => {
    render(
      <RescheduleAppointmentModal target={target} accessToken="tok" onClose={vi.fn()} onRescheduled={vi.fn()} conflictingTimes={[iso(13)]} />
    );
    const column = await tomorrowColumn();
    expect(within(column).getByText("10:00 AM")).toHaveAttribute("title", "Current appointment time");

    for (const label of ["10:00 AM", "12:00 PM", "1:00 PM", "2:00 PM"]) { // current, blocked, patient's other booking, no slot
      await userEvent.click(within(column).getByText(label));
      expect(screen.getByText("Select an available slot")).toBeInTheDocument();
    }

    await userEvent.click(within(column).getByText("11:00 AM"));
    expect(screen.getByText(/^New time:/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm Reschedule" })).toBeEnabled();
  });

  it("reschedules to the picked slot in UTC, then refreshes and closes", async () => {
    vi.mocked(api.rescheduleAppointment).mockResolvedValue({ id: "apt-1", appointment_time: iso(11), status: "CONFIRMED" });
    const alert = vi.spyOn(window, "alert").mockImplementation(() => {});
    const onRescheduled = vi.fn();
    const onClose = vi.fn();
    render(<RescheduleAppointmentModal target={target} accessToken="tok" onClose={onClose} onRescheduled={onRescheduled} />);

    await userEvent.click(within(await tomorrowColumn()).getByText("11:00 AM"));
    await userEvent.click(screen.getByRole("button", { name: "Confirm Reschedule" }));

    expect(api.rescheduleAppointment).toHaveBeenCalledWith("tok", "apt-1", iso(11));
    expect(onRescheduled).toHaveBeenCalled();
    expect(alert).toHaveBeenCalledWith(expect.stringContaining("Appointment rescheduled to"));
    expect(onClose).toHaveBeenCalled();
  });

  it("shows the server's error and stays open", async () => {
    vi.mocked(api.rescheduleAppointment).mockRejectedValue(new Error("Requested slot is not available."));
    const onClose = vi.fn();
    render(<RescheduleAppointmentModal target={target} accessToken="tok" onClose={onClose} onRescheduled={vi.fn()} />);

    await userEvent.click(within(await tomorrowColumn()).getByText("11:00 AM"));
    await userEvent.click(screen.getByRole("button", { name: "Confirm Reschedule" }));

    expect(await screen.findByText("Requested slot is not available.")).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
  });
});
