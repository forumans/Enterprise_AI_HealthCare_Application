import { describe, expect, it } from "vitest";
import { formatIsoDate } from "./SupportSearchPanel";

describe("formatIsoDate", () => {
  it("formats an ISO date as MM/DD/YYYY without shifting by time zone", () => {
    expect(formatIsoDate("1985-03-07")).toBe("03/07/1985");
    expect(formatIsoDate("2000-01-01")).toBe("01/01/2000"); // would become 12/31/1999 via new Date() west of UTC
  });

  it("shows a dash when there is no date", () => {
    expect(formatIsoDate("")).toBe("—");
    expect(formatIsoDate("garbage")).toBe("—");
  });
});
