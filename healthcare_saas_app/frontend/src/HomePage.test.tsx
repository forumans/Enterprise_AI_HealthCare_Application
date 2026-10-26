import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route, useLocation } from "react-router-dom";
import { describe, it, expect, vi } from "vitest";
import { HomePage } from "./App";

vi.mock("./hooks", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./hooks")>()),
  useMedicalNewsAgent: () => ({ isLoading: false, data: [] }),
}));

function Path() {
  return <div data-testid="path">{useLocation().pathname}</div>;
}

function renderHome(role: string) {
  render(
    <MemoryRouter initialEntries={["/"]}>
      <Routes>
        <Route path="/" element={<HomePage auth={{ session: { role } }} />} />
        <Route path="*" element={<Path />} />
      </Routes>
    </MemoryRouter>
  );
}

const buttonLabels = () => screen.getAllByRole("button").map((b) => b.textContent);

describe("HomePage login buttons", () => {
  it("shows Support Staff Login before Patient Login and Doctor Login for a guest", () => {
    renderHome("GUEST");
    expect(buttonLabels()).toEqual(["Support Staff Login", "Patient Login", "Doctor Login"]);
  });

  it("opens the support staff login page", () => {
    renderHome("GUEST");
    fireEvent.click(screen.getByRole("button", { name: "Support Staff Login" }));
    expect(screen.getByTestId("path")).toHaveTextContent("/support/login");
  });

  it("hides Support Staff Login for signed-in support staff", () => {
    renderHome("SUPPORT_STAFF");
    expect(buttonLabels()).toEqual(["Patient Login", "Doctor Login"]);
  });

  it("hides Patient Login for a signed-in patient", () => {
    renderHome("PATIENT");
    expect(buttonLabels()).toEqual(["Support Staff Login", "Doctor Login"]);
  });
});
