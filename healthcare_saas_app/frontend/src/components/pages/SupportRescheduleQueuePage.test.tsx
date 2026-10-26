import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { SupportRescheduleQueuePage } from "./SupportRescheduleQueuePage";
import { ClinicTimeZoneContext } from "../../contexts/ClinicTimeZoneContext";
import { api } from "../../api";
import type { RescheduleQueueRow } from "../../types";

vi.mock("../../api", () => ({ api: { getRescheduleQueue: vi.fn(), cancelAppointment: vi.fn() } }));
// The real modal loads the doctor's calendar; here it only reports a successful reschedule
vi.mock("../common/RescheduleAppointmentModal", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../common/RescheduleAppointmentModal")>()),
  RescheduleAppointmentModal: ({ target, onRescheduled, onClose }: any) => (
    <div role="dialog">
      <button onClick={async () => { await onRescheduled(); onClose(); }}>Move {target.patientName}</button>
    </div>
  ),
}));

const row = (overrides: Partial<RescheduleQueueRow>): RescheduleQueueRow => ({
  id: "a", appointment_time: "2026-10-26T01:00:00+00:00", status: "CONFIRMED", urgent: false,
  doctor_id: "doc-1", doctor_name: "Dr One", patient_id: "p", patient_name: "Pat", patient_phone: "555-0101",
  patient_email: "pat@example.test", reason_category: "VACATION", reason_label: "Vacation", ...overrides,
});

const URGENT = row({ id: "soon", appointment_time: "2026-10-26T01:00:00+00:00", urgent: true, patient_name: "Sam Soon" });
const LATER = row({ id: "later", appointment_time: "2026-10-30T17:00:00+00:00", patient_name: "Lee Later", doctor_id: "doc-2", doctor_name: "Dr Two", reason_label: "Sick" });

function renderPage() {
  render(
    <ClinicTimeZoneContext.Provider value="America/Los_Angeles">
      <SupportRescheduleQueuePage auth={{ session: { accessToken: "tok" } }} />
    </ClinicTimeZoneContext.Provider>
  );
}

const bodyRows = async () => within((await screen.findAllByRole("rowgroup"))[1]).getAllByRole("row");

describe("SupportRescheduleQueuePage", () => {
  beforeEach(() => {
    vi.mocked(api.getRescheduleQueue).mockReset();
    vi.mocked(api.cancelAppointment).mockReset();
  });
  afterEach(() => vi.restoreAllMocks());

  it("lists urgent appointments first with their contact details and block reason", async () => {
    vi.mocked(api.getRescheduleQueue).mockResolvedValue([URGENT, LATER]);
    renderPage();
    const [first, second] = await bodyRows();
    expect(first).toHaveTextContent("Urgent");
    expect(first).toHaveTextContent("Sam Soon");
    expect(first).toHaveTextContent("555-0101");
    expect(first).toHaveTextContent("pat@example.test");
    expect(second).toHaveTextContent("Lee Later");
    expect(second).not.toHaveTextContent("Urgent");
    expect(second).toHaveTextContent("Sick");
    expect(api.getRescheduleQueue).toHaveBeenCalledWith("tok");
  });

  it("filters by doctor", async () => {
    vi.mocked(api.getRescheduleQueue).mockResolvedValue([URGENT, LATER]);
    renderPage();
    await bodyRows();
    fireEvent.change(screen.getByLabelText("Doctor"), { target: { value: "doc-2" } });
    const rows = await bodyRows();
    expect(rows).toHaveLength(1);
    expect(rows[0]).toHaveTextContent("Lee Later");
  });

  it("drops a rescheduled appointment after reloading and tells the menu badge", async () => {
    vi.mocked(api.getRescheduleQueue).mockResolvedValueOnce([URGENT, LATER]).mockResolvedValueOnce([LATER]);
    const alert = vi.spyOn(window, "alert").mockImplementation(() => {});
    const changed = vi.fn();
    window.addEventListener("hc:reschedule-queue-changed", changed);
    renderPage();
    const [first] = await bodyRows();
    fireEvent.click(within(first).getByRole("button", { name: "Reschedule" }));
    fireEvent.click(await screen.findByRole("button", { name: "Move Sam Soon" }));

    await waitFor(() => expect(screen.queryByText("Sam Soon")).toBeNull());
    expect(await bodyRows()).toHaveLength(1);
    expect(changed).toHaveBeenCalled();
    window.removeEventListener("hc:reschedule-queue-changed", changed);
    alert.mockRestore();
  });

  it("cancels only after the usual confirmation", async () => {
    vi.mocked(api.getRescheduleQueue).mockResolvedValueOnce([LATER]).mockResolvedValueOnce([]);
    vi.mocked(api.cancelAppointment).mockResolvedValue({ message: "Appointment cancelled." });
    const confirm = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
    vi.spyOn(window, "alert").mockImplementation(() => {});
    renderPage();
    const [only] = await bodyRows();
    fireEvent.click(within(only).getByRole("button", { name: "Cancel" }));
    expect(api.cancelAppointment).not.toHaveBeenCalled();
    expect(confirm.mock.calls[0][0]).toMatch(/^Cancel Lee Later's appointment with Dr Two on /);

    fireEvent.click(within(only).getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(api.cancelAppointment).toHaveBeenCalledWith("tok", "later"));
    expect(await screen.findByText("No appointments need rescheduling.")).toBeInTheDocument();
  });
});
