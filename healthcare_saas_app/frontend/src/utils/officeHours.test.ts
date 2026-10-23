import { describe, expect, it } from "vitest";
import { OFFICE_HOUR_SLOTS, parseServerDate } from "./index";

describe("OFFICE_HOUR_SLOTS", () => {
  it("runs hourly from 8:00 AM through the 11:00 PM slot", () => {
    expect(OFFICE_HOUR_SLOTS).toHaveLength(16);
    expect(OFFICE_HOUR_SLOTS[0]).toBe("8:00 AM");
    expect(OFFICE_HOUR_SLOTS).toContain("12:00 PM");
    expect(OFFICE_HOUR_SLOTS).toContain("4:00 PM");
    expect(OFFICE_HOUR_SLOTS[OFFICE_HOUR_SLOTS.length - 1]).toBe("11:00 PM");
  });
});

describe("parseServerDate", () => {
  it("parses timestamptz output with an explicit offset and legacy naive-UTC output identically", () => {
    expect(parseServerDate("2026-11-02T13:00:00+00:00").getTime()).toBe(
      parseServerDate("2026-11-02T13:00:00").getTime()
    );
  });
});
