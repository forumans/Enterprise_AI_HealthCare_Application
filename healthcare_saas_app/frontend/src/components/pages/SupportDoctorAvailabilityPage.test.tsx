import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { SupportDoctorAvailabilityPage } from "./SupportDoctorAvailabilityPage";
import { ClinicTimeZoneContext } from "../../contexts/ClinicTimeZoneContext";
import { api } from "../../api";

vi.mock("../../api", () => ({
  api: { listAllDoctorAvailability: vi.fn(), listScheduleBlocks: vi.fn(), previewRangeBlock: vi.fn(), getDoctorMe: vi.fn() },
}));
// Picking a doctor from the search results
vi.mock("../common/SupportSearchPanel", () => ({
  SupportSearchPanel: ({ onPick }: any) => (
    <button onClick={() => onPick({ id: "doc-9", name: "Dr Nine", specialty: "Cardiology", license_number: "L9" })}>Pick Dr Nine</button>
  ),
}));

describe("SupportDoctorAvailabilityPage", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-10-25T18:35:00Z"));
    vi.mocked(api.listAllDoctorAvailability).mockResolvedValue([]);
    vi.mocked(api.listScheduleBlocks).mockResolvedValue([]);
  });
  afterEach(() => vi.useRealTimers());

  it("blocks a range on the picked doctor's behalf", async () => {
    vi.mocked(api.previewRangeBlock).mockRejectedValue(new Error("stop after preview"));
    render(
      <ClinicTimeZoneContext.Provider value="America/Los_Angeles">
        <SupportDoctorAvailabilityPage auth={{ session: { accessToken: "staff-tok", role: "SUPPORT_STAFF" } }} />
      </ClinicTimeZoneContext.Provider>
    );
    fireEvent.click(screen.getByRole("button", { name: "Pick Dr Nine" }));
    await screen.findByRole("heading", { name: "Block or Unblock a Time Range" });
    await waitFor(() => expect(api.listScheduleBlocks).toHaveBeenCalledWith("staff-tok", "doc-9"));

    fireEvent.change(screen.getByLabelText("From date"), { target: { value: "2026-11-03" } });
    fireEvent.change(screen.getByLabelText("To date"), { target: { value: "2026-11-03" } });
    fireEvent.change(screen.getByLabelText(/^Reason/), { target: { value: "ADMINISTRATIVE" } });
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));

    await waitFor(() => expect(api.previewRangeBlock).toHaveBeenCalledWith("staff-tok", "doc-9", expect.objectContaining({
      start: "2026-11-03T17:00:00.000Z", end: "2026-11-04T01:00:00.000Z", reason_category: "ADMINISTRATIVE",
    })));
    expect(api.getDoctorMe).not.toHaveBeenCalled();
    expect(await screen.findByRole("alert")).toHaveTextContent("stop after preview");
  });
});
