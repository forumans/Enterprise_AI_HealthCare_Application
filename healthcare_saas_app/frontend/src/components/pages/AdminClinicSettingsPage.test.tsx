import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AdminClinicSettingsPage } from "./AdminClinicSettingsPage";
import { api } from "../../api";

vi.mock("../../api", () => ({ api: { getCurrentTenant: vi.fn(), updateCurrentTenant: vi.fn() } }));

const tenant = { id: "t1", name: "Sunrise Clinic", domain: "sunrise.test", timezone: "America/New_York" };

describe("AdminClinicSettingsPage", () => {
  beforeEach(() => {
    vi.mocked(api.getCurrentTenant).mockResolvedValue(tenant);
    vi.mocked(api.updateCurrentTenant).mockReset();
  });

  it("shows the clinic's current zone and saves a new one for the whole session", async () => {
    vi.mocked(api.updateCurrentTenant).mockResolvedValue({ ...tenant, timezone: "America/Los_Angeles", slots_moved: 112 });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const setSession = vi.fn();
    render(<AdminClinicSettingsPage auth={{ session: { accessToken: "tok" }, setSession }} />);

    const select = await screen.findByLabelText("Clinic Time Zone");
    expect(select).toHaveValue("America/New_York");
    expect(screen.getByRole("button", { name: "Save Time Zone" })).toBeDisabled();

    await userEvent.selectOptions(select, "America/Los_Angeles");
    expect(screen.getByText(/Booked appointments keep their exact time/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Save Time Zone" }));

    expect(api.updateCurrentTenant).toHaveBeenCalledWith("tok", { timezone: "America/Los_Angeles" });
    expect(await screen.findByText(/Clinic time zone set to America\/Los_Angeles\. 112 upcoming slot/)).toBeInTheDocument();
    // The signed-in session switches to the new zone straight away
    const update = setSession.mock.calls[0][0];
    expect(update({ accessToken: "tok", clinicTimezone: "America/New_York" })).toEqual({ accessToken: "tok", clinicTimezone: "America/Los_Angeles" });
  });

  it("does nothing when the admin cancels the confirmation", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<AdminClinicSettingsPage auth={{ session: { accessToken: "tok" }, setSession: vi.fn() }} />);

    await userEvent.selectOptions(await screen.findByLabelText("Clinic Time Zone"), "Europe/London");
    await userEvent.click(screen.getByRole("button", { name: "Save Time Zone" }));
    expect(api.updateCurrentTenant).not.toHaveBeenCalled();
  });

  it("shows the server's error", async () => {
    vi.mocked(api.updateCurrentTenant).mockRejectedValue(new Error("Unknown time zone."));
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<AdminClinicSettingsPage auth={{ session: { accessToken: "tok" }, setSession: vi.fn() }} />);

    await userEvent.selectOptions(await screen.findByLabelText("Clinic Time Zone"), "Europe/Paris");
    await userEvent.click(screen.getByRole("button", { name: "Save Time Zone" }));
    expect(await screen.findByText("Unknown time zone.")).toBeInTheDocument();
  });
});
