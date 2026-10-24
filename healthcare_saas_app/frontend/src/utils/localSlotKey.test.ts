import { describe, expect, it } from "vitest";
import { localSlotKey, parseServerDate } from "./index";

describe("localSlotKey", () => {
  it("keys a Date by its local wall-clock hour", () => {
    expect(localSlotKey(new Date(2026, 9, 22, 23, 0, 0))).toBe("2026-10-22T23:00:00");
    expect(localSlotKey(new Date(2026, 0, 5, 8, 0, 0))).toBe("2026-01-05T08:00:00");
  });

  it("matches an API UTC timestamp to the cell built from the same instant", () => {
    const instant = new Date(Date.UTC(2026, 9, 23, 3, 0, 0));
    const cell = new Date(instant.getFullYear(), instant.getMonth(), instant.getDate(), instant.getHours());
    expect(localSlotKey(parseServerDate("2026-10-23T03:00:00+00:00"))).toBe(localSlotKey(cell));
  });

  it("round-trips: a key parsed back as local time gives the same key", () => {
    const key = "2026-11-03T14:00:00";
    expect(localSlotKey(new Date(key))).toBe(key);
  });
});
