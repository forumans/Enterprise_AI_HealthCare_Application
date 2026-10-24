import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AdminResetPasswordPage } from "./AdminResetPasswordPage";
import { api } from "../../api";

vi.mock("../../api", () => ({
  api: {
    getResetPasswordRoles: vi.fn(),
    adminSearchUsers: vi.fn(),
    adminChangeEmailById: vi.fn(),
    adminResetPasswordById: vi.fn(),
  },
}));

const auth = { session: { accessToken: "tok" } };
const staff = {
  user_id: "u1", role: "SUPPORT_STAFF", name: "Sam Support", email: "staff@clinic.com", phone: "5551234567",
  address: "", date_of_birth: "", specialty: "", is_active: true, is_self: false,
};

async function pickStaff() {
  render(<AdminResetPasswordPage auth={auth} />);
  await userEvent.selectOptions(await screen.findByLabelText(/Role/), "SUPPORT_STAFF");
  await userEvent.type(screen.getByLabelText("Search"), "sam");
  await userEvent.click(screen.getByRole("button", { name: "Search" }));
  await userEvent.click(await screen.findByRole("button", { name: "Sam Support" }));
  return {
    emailForm: screen.getByRole("heading", { name: "Change Email" }).closest("form")!,
    passwordForm: screen.getByRole("heading", { name: "Reset Password" }).closest("form")!,
  };
}

describe("AdminResetPasswordPage", () => {
  beforeEach(() => {
    vi.mocked(api.getResetPasswordRoles).mockResolvedValue([{ value: "SUPPORT_STAFF", label: "Support Staff" }]);
    vi.mocked(api.adminSearchUsers).mockResolvedValue([staff]);
    vi.mocked(api.adminChangeEmailById).mockReset();
    vi.mocked(api.adminResetPasswordById).mockReset();
  });

  it("requires a role before searching", async () => {
    render(<AdminResetPasswordPage auth={auth} />);
    await userEvent.type(screen.getByLabelText("Search"), "sam");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(screen.getByText("Please select a role")).toBeInTheDocument();
    expect(api.adminSearchUsers).not.toHaveBeenCalled();
  });

  it("shows both forms for the clicked person with the current email highlighted", async () => {
    const { emailForm } = await pickStaff();
    expect(api.adminSearchUsers).toHaveBeenCalledWith("tok", "SUPPORT_STAFF", "sam");
    expect(within(emailForm).getByText("Current (old) email")).toBeInTheDocument();
    expect(within(emailForm).getByText("staff@clinic.com")).toHaveStyle({ color: "#ffd28a" });
    expect(within(emailForm).getByText(/Type the new email in both boxes/)).toBeInTheDocument();
    // New email boxes start empty and aren't login-type fields browsers autofill
    for (const box of [within(emailForm).getByLabelText(/^New Email/, { selector: "input" }), within(emailForm).getByLabelText(/Confirm New Email/, { selector: "input" })]) {
      expect(box).toHaveValue("");
      expect(box).toHaveAttribute("type", "text");
      expect(box).toHaveAttribute("autocomplete", "off");
    }
  });

  it("explains old-then-new entry instead of sending it", async () => {
    const { emailForm } = await pickStaff();
    await userEvent.type(within(emailForm).getByLabelText(/^New Email/, { selector: "input" }), "staff@clinic.com");
    await userEvent.type(within(emailForm).getByLabelText(/Confirm New Email/, { selector: "input" }), "staff1@clinic.com");
    await userEvent.click(within(emailForm).getByRole("button", { name: "Change Email" }));

    expect(within(emailForm).getByText("The new email (staff@clinic.com) is the same as the current one (staff@clinic.com)")).toBeInTheDocument();
    expect(api.adminChangeEmailById).not.toHaveBeenCalled();
  });

  it("rejects mismatched entries", async () => {
    const { emailForm } = await pickStaff();
    await userEvent.type(within(emailForm).getByLabelText(/^New Email/, { selector: "input" }), "staff1@clinic.com");
    await userEvent.type(within(emailForm).getByLabelText(/Confirm New Email/, { selector: "input" }), "staff2@clinic.com");
    await userEvent.click(within(emailForm).getByRole("button", { name: "Change Email" }));
    expect(within(emailForm).getByText("The two new email entries do not match")).toBeInTheDocument();
  });

  it("changes the email by user id after confirmation and updates the display", async () => {
    const { emailForm } = await pickStaff();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.mocked(api.adminChangeEmailById).mockResolvedValue({ message: "ok", user_id: "u1", old_email: "staff@clinic.com", new_email: "staff1@clinic.com", user_role: "SUPPORT_STAFF" });
    await userEvent.type(within(emailForm).getByLabelText(/^New Email/, { selector: "input" }), "staff1@clinic.com");
    await userEvent.type(within(emailForm).getByLabelText(/Confirm New Email/, { selector: "input" }), "staff1@clinic.com");
    await userEvent.click(within(emailForm).getByRole("button", { name: "Change Email" }));

    expect(api.adminChangeEmailById).toHaveBeenCalledWith("tok", "u1", "staff1@clinic.com");
    expect(await within(emailForm).findByText("Email changed from staff@clinic.com to staff1@clinic.com")).toBeInTheDocument();
    expect(within(emailForm).getByText("staff1@clinic.com")).toBeInTheDocument(); // the highlighted current email
    expect(within(emailForm).getByLabelText(/^New Email/, { selector: "input" })).toHaveValue("");
  });

  it("keeps the typed email when the confirmation is cancelled", async () => {
    const { emailForm } = await pickStaff();
    vi.spyOn(window, "confirm").mockReturnValue(false);
    await userEvent.type(within(emailForm).getByLabelText(/^New Email/, { selector: "input" }), "staff1@clinic.com");
    await userEvent.type(within(emailForm).getByLabelText(/Confirm New Email/, { selector: "input" }), "staff1@clinic.com");
    await userEvent.click(within(emailForm).getByRole("button", { name: "Change Email" }));

    expect(api.adminChangeEmailById).not.toHaveBeenCalled();
    expect(within(emailForm).getByLabelText(/^New Email/, { selector: "input" })).toHaveValue("staff1@clinic.com");
  });

  it("validates and resets the password by user id", async () => {
    const { passwordForm } = await pickStaff();
    const [password, confirm] = [within(passwordForm).getByLabelText(/^New Password/, { selector: "input" }), within(passwordForm).getByLabelText(/Confirm New Password/, { selector: "input" })];
    await userEvent.type(password, "short");
    await userEvent.type(confirm, "short");
    await userEvent.click(within(passwordForm).getByRole("button", { name: "Reset Password" }));
    expect(within(passwordForm).getByText("Password must be at least 8 characters long")).toBeInTheDocument();

    vi.mocked(api.adminResetPasswordById).mockResolvedValue({ message: "ok", user_id: "u1", user_email: "staff@clinic.com", user_role: "SUPPORT_STAFF" });
    await userEvent.clear(password);
    await userEvent.clear(confirm);
    await userEvent.type(password, "BrandNew123");
    await userEvent.type(confirm, "BrandNew123");
    await userEvent.click(within(passwordForm).getByRole("button", { name: "Reset Password" }));
    expect(api.adminResetPasswordById).toHaveBeenCalledWith("tok", "u1", "BrandNew123");
    expect(await within(passwordForm).findByText("Password reset for Sam Support (staff@clinic.com)")).toBeInTheDocument();
  });
});
