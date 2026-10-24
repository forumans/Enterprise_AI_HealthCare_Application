import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { LoginPage } from "./LoginPage";
import { useAuthContext } from "../../contexts/AuthContext";

vi.mock("../../contexts/AuthContext", () => ({ useAuthContext: vi.fn() }));

function renderLogin(role: "SUPPORT_STAFF" | "DOCTOR", form = { email: "", password: "" }) {
  const handleLogin = vi.fn();
  vi.mocked(useAuthContext).mockReturnValue({
    loginForm: form,
    setLoginForm: vi.fn(),
    handleLogin,
    status: "",
    setStatus: vi.fn(),
  } as any);
  render(
    <MemoryRouter>
      <LoginPage role={role} />
    </MemoryRouter>
  );
  return handleLogin;
}

describe("LoginPage for support staff", () => {
  it("is titled for support staff and has no self-registration link", () => {
    renderLogin("SUPPORT_STAFF");
    expect(screen.getByRole("heading", { name: "Support Staff Login" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Login as Support Staff" })).toBeInTheDocument();
    expect(screen.getByText("Support staff accounts are created by an administrator")).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("logs in with the SUPPORT_STAFF role", async () => {
    const handleLogin = renderLogin("SUPPORT_STAFF", { email: "sam@clinic.com", password: "Password123" });
    await userEvent.click(screen.getByRole("button", { name: "Login as Support Staff" }));
    expect(handleLogin).toHaveBeenCalledWith("SUPPORT_STAFF");
  });

  it("still offers doctors a registration link", () => {
    renderLogin("DOCTOR");
    expect(screen.getByRole("link", { name: "New doctor? Register here" })).toHaveAttribute("href", "/doctors/register");
  });
});
