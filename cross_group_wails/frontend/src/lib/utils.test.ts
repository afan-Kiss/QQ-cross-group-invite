import { describe, expect, it } from "vitest";
import { formatDateTime, hasMojibake, toEpochMs } from "./utils";

describe("toEpochMs", () => {
  it("converts seconds to ms", () => {
    expect(toEpochMs(1_700_000_000)).toBe(1_700_000_000_000);
  });
  it("keeps milliseconds", () => {
    expect(toEpochMs(1_700_000_000_000)).toBe(1_700_000_000_000);
  });
  it("handles string seconds", () => {
    expect(toEpochMs("1700000000")).toBe(1_700_000_000_000);
  });
});

describe("formatDateTime", () => {
  it("does not render 1970 for second timestamps", () => {
    const text = formatDateTime(1_700_000_000);
    expect(text.includes("1970")).toBe(false);
  });
});

describe("hasMojibake", () => {
  it("detects ascii question marks", () => {
    expect(hasMojibake("?".repeat(4))).toBe(true);
    expect(hasMojibake("ok")).toBe(false);
  });
});
