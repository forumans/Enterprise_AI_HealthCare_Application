/**
 * Vitest setup for component tests: jest-dom matchers (toBeInTheDocument, toHaveStyle, ...) and
 * unmounting rendered components between tests.
 */

import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks(); // undo vi.spyOn (window.confirm, alert, ...)
  vi.clearAllMocks(); // forget calls to module mocks, so "not called" checks start fresh
});
