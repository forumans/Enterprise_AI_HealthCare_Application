import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { LoginPage } from "./LoginPage";
import { useAuthContext } from "../../contexts/AuthContext";
import { api } from "../../api";

vi.mock("../../contexts/AuthContext", () => ({ useAuthContext: vi.fn() }));
vi.mock("../../api", () => ({ api: { getAdminSetupStatus: vi.fn() } }));

function renderLogin(role: "SUPPORT_STAFF" | "DOCTOR" | "ADMIN", form = { email: "", password: "" }) {
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
    expect(screen.queryByRole("link", { name: /register/i })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Forgot password?" })).toHaveAttribute("href", "/forgot-password");
  });

  it("leaves the password length to the server (an older account may have a shorter password)", async () => {
    const handleLogin = renderLogin("DOCTOR", { email: "old@clinic.com", password: "short" });
    await userEvent.click(screen.getByRole("button", { name: "Login as Doctor" }));
    expect(handleLogin).toHaveBeenCalledWith("DOCTOR");
    expect(vi.mocked(useAuthContext).mock.results[0].value.setStatus).not.toHaveBeenCalledWith(expect.stringMatching(/at least 8/));
  });

  it("logs in with the SUPPORT_STAFF role", async () => {
    const handleLogin = renderLogin("SUPPORT_STAFF", { email: "sam@clinic.com", password: "Password123" });
    await userEvent.click(screen.getByRole("button", { name: "Login as Support Staff" }));
    expect(handleLogin).toHaveBeenCalledWith("SUPPORT_STAFF");
  });

  it("explains why the user is back on the login page after the session ended", () => {
    vi.mocked(useAuthContext).mockReturnValue({ loginForm: { email: "", password: "" }, setLoginForm: vi.fn(), handleLogin: vi.fn(), status: "", setStatus: vi.fn() } as any);
    render(
      <MemoryRouter initialEntries={[{ pathname: "/support/login", state: { notice: "Your session has ended. Please sign in again." } }]}>
        <LoginPage role="SUPPORT_STAFF" />
      </MemoryRouter>
    );
    expect(screen.getByRole("status")).toHaveTextContent("Your session has ended. Please sign in again.");
  });

  it("shows no notice on a normal visit", () => {
    renderLogin("SUPPORT_STAFF");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("still offers doctors a registration link", () => {
    renderLogin("DOCTOR");
    expect(screen.getByRole("link", { name: "New doctor? Register here" })).toHaveAttribute("href", "/doctors/register");
  });
});

describe("LoginPage for admins", () => {
  it("offers first-time setup only while no administrator exists", async () => {
    vi.mocked(api.getAdminSetupStatus).mockResolvedValue({ setup_required: true });
    renderLogin("ADMIN");
    expect(await screen.findByRole("link", { name: "First time setup? Create the first administrator" })).toHaveAttribute("href", "/admin/setup");
  });

  it("points to existing administrators once the system is set up", async () => {
    vi.mocked(api.getAdminSetupStatus).mockResolvedValue({ setup_required: false });
    renderLogin("ADMIN");
    expect(await screen.findByText("Administrator accounts are created by an existing administrator")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /setup|register/i })).not.toBeInTheDocument();
  });
});
