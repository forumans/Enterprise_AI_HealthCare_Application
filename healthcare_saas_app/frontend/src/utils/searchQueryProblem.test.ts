import { describe, expect, it } from "vitest";
import { searchQueryProblem } from "./index";

describe("searchQueryProblem", () => {
  it("accepts 2+ characters and the * wildcard", () => {
    expect(searchQueryProblem("st", "a name")).toBe("");
    expect(searchQueryProblem("*", "a name")).toBe("");
    expect(searchQueryProblem("  *  ", "a name")).toBe("");
  });

  it("rejects shorter searches and explains the wildcard", () => {
    expect(searchQueryProblem("s", "a name or phone number")).toBe("Enter at least 2 characters of a name or phone number, or * to list everyone.");
    expect(searchQueryProblem("   ", "a name")).not.toBe("");
  });
});
