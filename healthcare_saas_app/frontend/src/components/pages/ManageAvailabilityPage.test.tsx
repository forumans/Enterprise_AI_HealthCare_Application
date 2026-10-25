import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { ManageAvailabilityPage } from "./ManageAvailabilityPage";
import { ClinicTimeZoneContext } from "../../contexts/ClinicTimeZoneContext";
import { api } from "../../api";

vi.mock("../../api", () => ({ api: { listAllDoctorAvailability: vi.fn(), upsertDoctorAvailability: vi.fn(), getDoctorMe: vi.fn() } }));

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
    expect(screen.getByTestId("clinic-time-note")).toHaveTextContent("All times are clinic time: PDT (America/Los Angeles)");

    // Today: hours that have passed (8-11 AM) are hidden, noon onwards can be edited
    const eight = await rowFor("8:00 AM");
    expect(within(eight[1]).queryByRole("button")).toBeNull();
    expect(within((await rowFor("12:00 PM"))[1]).getByRole("button", { name: "Click to Add" })).toBeInTheDocument();
    // Every later day offers the whole 8 AM - 11 PM range
    for (const cell of eight.slice(2)) {
      expect(within(cell).getByRole("button", { name: "Click to Add" })).toBeInTheDocument();
    }
  });
});
