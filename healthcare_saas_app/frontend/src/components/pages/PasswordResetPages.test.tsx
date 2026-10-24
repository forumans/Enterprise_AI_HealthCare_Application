import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { ForgotPasswordPage } from "./ForgotPasswordPage";
import { ResetPasswordPage } from "./ResetPasswordPage";
import { api } from "../../api";

vi.mock("../../api", () => ({
  api: { forgotPassword: vi.fn(), resetPassword: vi.fn() },
}));

const GENERIC = "If an account exists for that email, a password reset link has been sent.";

describe("ForgotPasswordPage", () => {
  it("validates the email before sending", async () => {
    render(<MemoryRouter><ForgotPasswordPage /></MemoryRouter>);
    // The browser's own email check blocks "no @" input; "name@host" gets past it but not ours
    await userEvent.type(screen.getByLabelText(/^Email/, { selector: "input" }), "sam@clinic");
    await userEvent.click(screen.getByRole("button", { name: "Send Reset Link" }));
    expect(screen.getByText("Please enter a valid email address.")).toBeInTheDocument();
    expect(api.forgotPassword).not.toHaveBeenCalled();
  });

  it("requests a link and shows the same reply whatever the email", async () => {
    vi.mocked(api.forgotPassword).mockResolvedValue({ message: GENERIC });
    render(<MemoryRouter><ForgotPasswordPage /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText(/^Email/, { selector: "input" }), " sam@clinic.com ");
    await userEvent.click(screen.getByRole("button", { name: "Send Reset Link" }));

    expect(api.forgotPassword).toHaveBeenCalledWith("sam@clinic.com");
    expect(await screen.findByText(GENERIC)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Send Reset Link" })).not.toBeInTheDocument();
  });
});

function renderReset(url: string) {
  render(<MemoryRouter initialEntries={[url]}><ResetPasswordPage /></MemoryRouter>);
}

describe("ResetPasswordPage", () => {

  it("explains that the email link is needed when there is no token", () => {
    renderReset("/reset-password");
    expect(screen.getByText("This page needs the link from your password reset email.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Request a new reset link" })).toHaveAttribute("href", "/forgot-password");
  });

  it("checks length and matching before sending", async () => {
    renderReset("/reset-password?token=abc");
    const [password, confirm] = [screen.getByLabelText(/^New Password/, { selector: "input" }), screen.getByLabelText(/Confirm New Password/, { selector: "input" })];

    await userEvent.type(password, "short");
    await userEvent.type(confirm, "short");
    await userEvent.click(screen.getByRole("button", { name: "Set New Password" }));
    expect(screen.getByText("Password must be at least 8 characters long.")).toBeInTheDocument();

    await userEvent.clear(password);
    await userEvent.clear(confirm);
    await userEvent.type(password, "LongEnough1");
    await userEvent.type(confirm, "LongEnough2");
    await userEvent.click(screen.getByRole("button", { name: "Set New Password" }));
    expect(screen.getByText("The two passwords do not match.")).toBeInTheDocument();
    expect(api.resetPassword).not.toHaveBeenCalled();
  });

  it("sets the new password with the token from the link", async () => {
    vi.mocked(api.resetPassword).mockResolvedValue({ message: "Your password has been reset. You can now sign in with your new password." });
    renderReset("/reset-password?token=tok-123");
    await userEvent.type(screen.getByLabelText(/^New Password/, { selector: "input" }), "BrandNew123");
    await userEvent.type(screen.getByLabelText(/Confirm New Password/, { selector: "input" }), "BrandNew123");
    await userEvent.click(screen.getByRole("button", { name: "Set New Password" }));

    expect(api.resetPassword).toHaveBeenCalledWith("tok-123", "BrandNew123");
    expect(await screen.findByText(/Your password has been reset/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to sign in" })).toBeInTheDocument();
  });

  it("shows the server's message for an expired or used link", async () => {
    vi.mocked(api.resetPassword).mockImplementation(() => Promise.reject(new Error("This password reset link is invalid or has expired. Please request a new one.")));
    renderReset("/reset-password?token=old");
    await userEvent.type(screen.getByLabelText(/^New Password/, { selector: "input" }), "BrandNew123");
    await userEvent.type(screen.getByLabelText(/Confirm New Password/, { selector: "input" }), "BrandNew123");
    await userEvent.click(screen.getByRole("button", { name: "Set New Password" }));
    expect(await screen.findByText(/invalid or has expired/)).toBeInTheDocument();
  });
});
