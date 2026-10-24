import { describe, expect, it, vi, afterEach } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider, SESSION_ENDED_NOTICE, useAuthContext } from "./AuthContext";
import { request, SESSION_ENDED_EVENT } from "../api";

function respondWith(status: number) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "nope" }), { status })));
}

describe("api request: session-ended signal", () => {
  afterEach(() => vi.unstubAllGlobals());

  async function signalled(status: number, headers: Record<string, string>) {
    respondWith(status);
    const listener = vi.fn();
    window.addEventListener(SESSION_ENDED_EVENT, listener);
    await request("/anything", { method: "GET", headers }).catch(() => {});
    window.removeEventListener(SESSION_ENDED_EVENT, listener);
    return listener.mock.calls.length;
  }

  it("signals when a request carrying a login token is refused with 401", async () => {
    expect(await signalled(401, { Authorization: "Bearer t" })).toBe(1);
  });

  it("stays quiet for a wrong password (no token sent) and for other errors", async () => {
    expect(await signalled(401, {})).toBe(0); // e.g. the login request itself
    expect(await signalled(403, { Authorization: "Bearer t" })).toBe(0); // forbidden is not a dead session
    expect(await signalled(500, { Authorization: "Bearer t" })).toBe(0);
  });
});

/** Shows where we are and what the auth context holds, and lets the test sign in as a role. */
function Probe({ role }: { role?: "DOCTOR" | "SUPPORT_STAFF" }) {
  const { session, setSession } = useAuthContext();
  const location = useLocation();
  return (
    <div>
      <span data-testid="path">{location.pathname}</span>
      <span data-testid="role">{session.role}</span>
      <span data-testid="notice">{(location.state as { notice?: string } | null)?.notice ?? ""}</span>
      {role && <button onClick={() => setSession({ accessToken: "tok", role, tenantId: "t" })}>sign in</button>}
    </div>
  );
}

function renderApp(start: string, role?: "DOCTOR" | "SUPPORT_STAFF") {
  render(
    <MemoryRouter initialEntries={[start]}>
      <AuthProvider>
        <Routes>
          <Route path="*" element={<Probe role={role} />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  );
}

const endSession = () => act(() => { window.dispatchEvent(new CustomEvent(SESSION_ENDED_EVENT)); });

describe("AuthContext: graceful sign-out when the session ends", () => {
  it("signs out and sends the user to their role's login page with a notice", async () => {
    renderApp("/doctors/appointments", "DOCTOR");
    act(() => screen.getByRole("button", { name: "sign in" }).click());
    expect(screen.getByTestId("role")).toHaveTextContent("DOCTOR");

    endSession();

    expect(screen.getByTestId("role")).toHaveTextContent("GUEST");
    expect(screen.getByTestId("path")).toHaveTextContent("/doctors/login");
    expect(screen.getByTestId("notice")).toHaveTextContent(SESSION_ENDED_NOTICE);
  });

  it("handles several failing requests at once with a single sign-out", async () => {
    renderApp("/support/patient-appointments", "SUPPORT_STAFF");
    act(() => screen.getByRole("button", { name: "sign in" }).click());

    endSession();
    endSession();
    endSession();

    expect(screen.getByTestId("path")).toHaveTextContent("/support/login");
    expect(screen.getByTestId("role")).toHaveTextContent("GUEST");
  });

  it("ignores the signal for guests", () => {
    renderApp("/patients/register");
    endSession();
    expect(screen.getByTestId("path")).toHaveTextContent("/patients/register");
    expect(screen.getByTestId("notice")).toHaveTextContent("");
  });
});
