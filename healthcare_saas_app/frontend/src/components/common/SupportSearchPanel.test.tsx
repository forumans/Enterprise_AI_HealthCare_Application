import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SupportSearchPanel } from "./SupportSearchPanel";
import { api } from "../../api";

vi.mock("../../api", () => ({
  api: { supportSearchPatients: vi.fn(), supportSearchDoctors: vi.fn() },
}));

const doctors = [
  { id: "d1", name: "Dr One", phone: "555-0100", email: "doc1@x.test", specialty: "Cardiology", license_number: "L-1" },
  { id: "d2", name: "Dr Two", phone: "", email: "doc2@x.test", specialty: "", license_number: "" },
];

describe("SupportSearchPanel", () => {
  beforeEach(() => {
    vi.mocked(api.supportSearchDoctors).mockReset();
    vi.mocked(api.supportSearchPatients).mockReset();
  });

  it("rejects a one-character search without calling the server", async () => {
    render(<SupportSearchPanel kind="doctor" accessToken="t" onPick={vi.fn()} />);
    await userEvent.type(screen.getByLabelText("Find Doctor"), "d");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(screen.getByText(/at least 2 characters.*or \* to list everyone/)).toBeInTheDocument();
    expect(api.supportSearchDoctors).not.toHaveBeenCalled();
  });

  it("searches with * and lists numbered results with the doctor columns", async () => {
    vi.mocked(api.supportSearchDoctors).mockResolvedValue(doctors);
    render(<SupportSearchPanel kind="doctor" accessToken="tok" onPick={vi.fn()} />);
    await userEvent.type(screen.getByLabelText("Find Doctor"), "*");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(api.supportSearchDoctors).toHaveBeenCalledWith("tok", "*");
    const rows = await screen.findAllByRole("row");
    expect(within(rows[0]).getAllByRole("columnheader").map(h => h.textContent)).toEqual(["#", "Full Name", "Phone", "Email", "Specialty", "License Number"]);
    expect(within(rows[1]).getAllByRole("cell").map(c => c.textContent)).toEqual(["1", "Dr One", "555-0100", "doc1@x.test", "Cardiology", "L-1"]);
    expect(within(rows[2]).getAllByRole("cell").map(c => c.textContent)).toEqual(["2", "Dr Two", "—", "doc2@x.test", "General Practice", "—"]);
    expect(screen.getByText("2 doctors found. Click a name to continue.")).toBeInTheDocument();
  });

  it("makes full names links that pick the person, and highlights the picked row", async () => {
    vi.mocked(api.supportSearchDoctors).mockResolvedValue(doctors);
    const onPick = vi.fn();
    const { rerender } = render(<SupportSearchPanel kind="doctor" accessToken="t" onPick={onPick} />);
    await userEvent.type(screen.getByLabelText("Find Doctor"), "dr");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));
    await userEvent.click(await screen.findByRole("button", { name: "Dr Two" }));

    expect(onPick).toHaveBeenCalledWith(doctors[1]);
    rerender(<SupportSearchPanel kind="doctor" accessToken="t" onPick={onPick} selectedId="d2" />);
    expect(screen.getByRole("button", { name: "Dr Two" }).closest("tr")).toHaveStyle({ backgroundColor: "rgba(66, 181, 245, 0.18)" });
  });

  it("shows patient columns and a no-match message", async () => {
    vi.mocked(api.supportSearchPatients).mockResolvedValueOnce([
      { id: "p1", name: "Steve Works", phone: "(555) 010-2030", email: "s@x.test", date_of_birth: "1985-03-07", gender: "Male", insurance_provider: "Acme", city: "Austin", state: "TX" },
    ]).mockResolvedValueOnce([]);
    render(<SupportSearchPanel kind="patient" accessToken="t" onPick={vi.fn()} />);
    const box = screen.getByLabelText("Find Patient");
    await userEvent.type(box, "steve");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));

    const cells = within((await screen.findAllByRole("row"))[1]).getAllByRole("cell").map(c => c.textContent);
    expect(cells).toEqual(["1", "Steve Works", "(555) 010-2030", "s@x.test", "03/07/1985", "Male", "Acme", "Austin, TX"]);

    await userEvent.clear(box);
    await userEvent.type(box, "nobody");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(await screen.findByText('No patients match "nobody"')).toBeInTheDocument();
  });
});
