import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { ManageAvailabilityPage } from "./ManageAvailabilityPage";
import { ClinicTimeZoneContext } from "../../contexts/ClinicTimeZoneContext";
import { api } from "../../api";

vi.mock("../../api", () => ({
  api: {
    listAllDoctorAvailability: vi.fn(), upsertDoctorAvailability: vi.fn(), getDoctorMe: vi.fn(),
    listScheduleBlocks: vi.fn(), previewRangeBlock: vi.fn(), applyRangeBlock: vi.fn(), previewRangeUnblock: vi.fn(), applyRangeUnblock: vi.fn(),
  },
}));

const CLINIC_ZONE = "America/Los_Angeles";
const doctor = { id: "doc-1", name: "Dr One" };

/** The grid's row for one hourly label: [time label, day 1, ..., day 7]. */
async function rowFor(label: string) {
  const table = await screen.findByRole("table");
  const row = within(table).getAllByRole("row").find(r => within(r).queryAllByRole("cell")[0]?.textContent === label);
  return within(row as HTMLElement).getAllByRole("cell");
}

describe("ManageAvailabilityPage", () => {
  beforeEach(() => {
    // Sunday Oct 25, 2026, 11:35 AM in the clinic (Los Angeles); the test runner's zone is Tokyo
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-10-25T18:35:00Z"));
    vi.mocked(api.listAllDoctorAvailability).mockResolvedValue([]);
    vi.mocked(api.listScheduleBlocks).mockResolvedValue([]);
  });
  afterEach(() => vi.useRealTimers());

  it("starts the grid today in clinic time, so a Sunday isn't a week of past days", async () => {
    render(
      <ClinicTimeZoneContext.Provider value={CLINIC_ZONE}>
        <ManageAvailabilityPage auth={{ session: { accessToken: "tok" } }} doctor={doctor} />
      </ClinicTimeZoneContext.Provider>
    );

    const headers = within(await screen.findByRole("table")).getAllByRole("columnheader");
    expect(headers[1]).toHaveTextContent("Sun10/25/2026");
    expect(headers[7]).toHaveTextContent("Sat10/31/2026");
    expect(screen.getAllByTestId("clinic-time-note")[0]).toHaveTextContent("All times are clinic time: PDT (America/Los Angeles)");

    // Today: hours that have passed (8-11 AM) are hidden, noon onwards can be edited
    const eight = await rowFor("8:00 AM");
    expect(within(eight[1]).queryByRole("button")).toBeNull();
    expect(within((await rowFor("12:00 PM"))[1]).getByRole("button", { name: "Click to Add" })).toBeInTheDocument();
    // Every later day offers the whole 8 AM - 11 PM range
    for (const cell of eight.slice(2)) {
      expect(within(cell).getByRole("button", { name: "Click to Add" })).toBeInTheDocument();
    }
  });

  function renderPage() {
    render(
      <ClinicTimeZoneContext.Provider value={CLINIC_ZONE}>
        <ManageAvailabilityPage auth={{ session: { accessToken: "tok" } }} doctor={doctor} />
      </ClinicTimeZoneContext.Provider>
    );
  }

  it("stops at the fifth week, since slots can be changed only 30 days ahead", async () => {
    renderPage();
    const next = await screen.findByRole("button", { name: "Next Week" });
    for (let week = 0; week < 4; week++) {
      expect(next).toBeEnabled();
      fireEvent.click(next);
      await screen.findByRole("table");
    }
    expect(next).toBeDisabled();
    expect(screen.getByRole("button", { name: "Previous Week" })).toBeEnabled();
  });

  it("asks for confirmation (not a reason) before unblocking, and sends no reason", async () => {
    // 12:00 PM PDT today is blocked
    vi.mocked(api.listAllDoctorAvailability).mockResolvedValue([{ slot_time: "2026-10-25T19:00:00+00:00", status: "BLOCKED" }]);
    vi.mocked(api.upsertDoctorAvailability).mockResolvedValue({ message: "Slot unblocked successfully" });
    const prompt = vi.spyOn(window, "prompt");
    const confirm = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
    renderPage();
    const blocked = within((await rowFor("12:00 PM"))[1]).getByRole("button", { name: "Blocked" });

    fireEvent.click(blocked);  // cancelled
    await waitFor(() => expect(confirm).toHaveBeenCalledTimes(1));
    expect(api.upsertDoctorAvailability).not.toHaveBeenCalled();

    fireEvent.click(blocked);
    await waitFor(() => expect(api.upsertDoctorAvailability).toHaveBeenCalledWith("doc-1", "2026-10-25T19:00:00.000Z", true, "tok"));
    expect(confirm).toHaveBeenLastCalledWith("Unblock this slot? Patients will be able to book it again.");
    expect(prompt).not.toHaveBeenCalled();
    confirm.mockRestore();
    prompt.mockRestore();
  });

  it("labels a booked slot in a blocked hour 'Booked – Needs reschedule' and keeps it unclickable", async () => {
    // Monday 12:00 PM PDT is booked and the doctor has since blocked it
    vi.mocked(api.listAllDoctorAvailability).mockResolvedValue([
      { slot_time: "2026-10-26T19:00:00+00:00", status: "BOOKED", block_id: "b-1", block_reason: "Vacation", needs_reschedule: true },
      { slot_time: "2026-10-26T20:00:00+00:00", status: "BOOKED", block_id: null, block_reason: null, needs_reschedule: false },
    ]);
    renderPage();
    const flagged = within((await rowFor("12:00 PM"))[2]).getByRole("button", { name: /Booked – Needs reschedule/ });
    expect(flagged).toHaveTextContent("Booked – Needs reschedule");
    expect(flagged).toHaveAttribute("aria-disabled", "true");
    expect(flagged).toHaveAttribute("title", "Blocked: Vacation");
    fireEvent.click(flagged);
    expect(api.upsertDoctorAvailability).not.toHaveBeenCalled();
    expect(within((await rowFor("1:00 PM"))[2]).getByRole("button", { name: "Patient Booked" })).toBeDisabled();
  });
});

const PREVIEW = {
  mode: "block" as const, start: "2026-11-03T17:00:00+00:00", end: "2026-11-06T01:00:00+00:00",
  slots_to_create: 16, created_blocked: 8, to_block: 20, already_blocked: 2, to_flag: 1, already_flagged: 0,
  to_open: 0, already_open: 0, to_unflag: 0, days_to_fill: 1, fingerprint: "fp-1",
  appointments: [{ appointment_id: "apt-1", appointment_time: "2026-11-04T18:00:00+00:00", patient_name: "Pat Patient", status: "CONFIRMED", needs_reschedule: false }],
};

describe("ManageAvailabilityPage range block", () => {
  beforeEach(() => {
    // Sunday Oct 25, 2026, 11:35 AM in the clinic (Los Angeles)
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-10-25T18:35:00Z"));
    vi.mocked(api.listAllDoctorAvailability).mockResolvedValue([]);
    vi.mocked(api.listScheduleBlocks).mockResolvedValue([]);
    vi.mocked(api.previewRangeBlock).mockReset();
    vi.mocked(api.applyRangeBlock).mockReset();
    vi.mocked(api.previewRangeUnblock).mockReset();
  });
  afterEach(() => vi.useRealTimers());

  async function renderPanel() {
    render(
      <ClinicTimeZoneContext.Provider value={CLINIC_ZONE}>
        <ManageAvailabilityPage auth={{ session: { accessToken: "tok" } }} doctor={doctor} />
      </ClinicTimeZoneContext.Provider>
    );
    await screen.findByRole("heading", { name: "Block or Unblock a Time Range" });
  }

  function fillRange(from: string, fromHour: string, to: string, toHour: string) {
    fireEvent.change(screen.getByLabelText("From date"), { target: { value: from } });
    fireEvent.change(screen.getByLabelText("From hour"), { target: { value: fromHour } });
    fireEvent.change(screen.getByLabelText("To date"), { target: { value: to } });
    fireEvent.change(screen.getByLabelText("To hour (not included)"), { target: { value: toHour } });
  }

  const reason = (value: string) => fireEvent.change(screen.getByLabelText(/^Reason/), { target: { value } });
  const preview = () => fireEvent.click(screen.getByRole("button", { name: "Preview" }));

  it("checks the range and reason before previewing", async () => {
    await renderPanel();
    const cases: Array<[() => void, string]> = [
      [() => { fillRange("2026-11-05", "9", "2026-11-03", "17"); reason("VACATION"); }, "End must be after start."],
      [() => { fillRange("2026-11-03", "12", "2026-11-03", "12"); }, "End must be after start."],
      [() => { fillRange("2026-11-03", "9", "2026-11-03", "17"); reason(""); }, "Please choose a reason."],
      [() => { reason("OTHER"); }, "Please describe the reason."],
      [() => { reason("VACATION"); fillRange("2026-11-03", "9", "2027-06-01", "17"); }, "Cannot change slots beyond 180 days."],
      [() => { fillRange("2026-10-20", "9", "2026-10-21", "17"); }, "Range is entirely in the past."],
    ];
    for (const [arrange, message] of cases) {
      arrange();
      preview();
      expect(await screen.findByRole("alert")).toHaveTextContent(message);
    }
    expect(api.previewRangeBlock).not.toHaveBeenCalled();
  });

  it("sends the clinic-time range as UTC, half-open, with the reason", async () => {
    vi.mocked(api.previewRangeBlock).mockResolvedValue({ ...PREVIEW, appointments: [] });
    await renderPanel();
    // Nov 3 9 AM to Nov 5 5 PM Pacific (after the clocks change on Nov 1: UTC-8)
    fillRange("2026-11-03", "9", "2026-11-05", "17");
    reason("CONFERENCE");
    fireEvent.change(screen.getByLabelText(/^Note/), { target: { value: " Cardiology summit " } });
    preview();
    await waitFor(() => expect(api.previewRangeBlock).toHaveBeenCalledWith("tok", "doc-1", {
      start: "2026-11-03T17:00:00.000Z", end: "2026-11-06T01:00:00.000Z", reason_category: "CONFERENCE", reason_note: "Cardiology summit",
    }));

    // All day: 8 AM on the first date to the end of the last date
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    fireEvent.click(screen.getByLabelText("All day"));
    preview();
    await waitFor(() => expect(api.previewRangeBlock).toHaveBeenLastCalledWith("tok", "doc-1", expect.objectContaining({
      start: "2026-11-03T16:00:00.000Z", end: "2026-11-06T08:00:00.000Z",
    })));
  });

  it("needs the conflicts acknowledged before confirming, then applies with the fingerprint", async () => {
    vi.mocked(api.previewRangeBlock).mockResolvedValue(PREVIEW);
    vi.mocked(api.applyRangeBlock).mockResolvedValue({ ...PREVIEW, message: "Range blocked.", block_id: "b-1", needs_reschedule: 1 });
    await renderPanel();
    fillRange("2026-11-03", "9", "2026-11-05", "17");
    reason("VACATION");
    preview();

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByTestId("range-counts")).toHaveTextContent("Slots to create: 16 (8 blocked)");
    expect(within(dialog).getByTestId("range-counts")).toHaveTextContent("Open slots to block: 20");
    expect(within(dialog).getByTestId("range-counts")).toHaveTextContent("Already blocked: 2");
    expect(within(dialog).getByText("Pat Patient")).toBeInTheDocument();
    const confirm = within(dialog).getByRole("button", { name: "Confirm" });
    expect(confirm).toBeDisabled();
    fireEvent.click(within(dialog).getByRole("checkbox"));
    expect(confirm).toBeEnabled();
    fireEvent.click(confirm);

    await waitFor(() => expect(api.applyRangeBlock).toHaveBeenCalledWith("tok", "doc-1", {
      start: "2026-11-03T17:00:00.000Z", end: "2026-11-06T01:00:00.000Z", reason_category: "VACATION", reason_note: undefined, fingerprint: "fp-1",
    }));
    expect(await screen.findByRole("status")).toHaveTextContent("Range blocked. 1 booked appointment(s) need rescheduling.");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("previews again when the schedule changed since the preview (409)", async () => {
    vi.mocked(api.previewRangeBlock)
      .mockResolvedValueOnce({ ...PREVIEW, appointments: [] })
      .mockResolvedValueOnce({ ...PREVIEW, fingerprint: "fp-2" });
    vi.mocked(api.applyRangeBlock).mockRejectedValueOnce(new Error("The schedule changed. Review the changes again."));
    await renderPanel();
    fillRange("2026-11-03", "9", "2026-11-05", "17");
    reason("SICK");
    preview();
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Confirm" }));

    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("The schedule changed. Review the changes again.");
    expect(api.previewRangeBlock).toHaveBeenCalledTimes(2);
    // The new booking now shows, and must be acknowledged again
    expect(within(dialog).getByText("Pat Patient")).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Confirm" })).toBeDisabled();
  });

  it("lists active blocks and 'Unblock all' previews the block's own range", async () => {
    vi.mocked(api.listScheduleBlocks).mockResolvedValue([
      {
        id: "b-1", start: "2026-11-03T17:00:00+00:00", end: "2026-11-06T01:00:00+00:00", reason_category: "VACATION", reason_label: "Vacation",
        reason_note: "Family", created_at: "2026-10-20T00:00:00+00:00", released_at: null, state: "PARTIALLY_RELEASED",
        blocked_hours: 30, needs_reschedule: 2, opened_hours: 4,
      },
      {
        id: "b-0", start: "2026-10-27T17:00:00+00:00", end: "2026-10-27T20:00:00+00:00", reason_category: "SICK", reason_label: "Sick",
        reason_note: null, created_at: "2026-10-20T00:00:00+00:00", released_at: "2026-10-21T00:00:00+00:00", state: "RELEASED",
        blocked_hours: 0, needs_reschedule: 0, opened_hours: 0,
      },
    ]);
    vi.mocked(api.previewRangeUnblock).mockResolvedValue({ ...PREVIEW, mode: "unblock", to_open: 30, to_unflag: 2, appointments: [] });
    await renderPanel();
    const row = (await screen.findByText("Vacation: Family")).closest("tr") as HTMLElement;
    expect(row).toHaveTextContent("Partially released");
    expect(within(row.closest("table") as HTMLElement).getAllByRole("row")).toHaveLength(2);  // released blocks aren't listed

    fireEvent.click(within(row).getByRole("button", { name: "Unblock all" }));
    await waitFor(() => expect(api.previewRangeUnblock).toHaveBeenCalledWith("tok", "doc-1", {
      start: "2026-11-03T17:00:00+00:00", end: "2026-11-06T01:00:00+00:00",
    }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByTestId("range-counts")).toHaveTextContent("Blocked slots to open: 30");
    expect(within(dialog).getByTestId("range-counts")).toHaveTextContent("Deleted hours are not restored.");
  });
});
