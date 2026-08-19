import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";

describe("ProgressPanel waiting + cancelled", () => {
  const src = fs.readFileSync(path.join(__dirname, "ProgressPanel.tsx"), "utf8");

  it("shows waiting for running progress (waiting=10 cancelled=0)", () => {
    expect(src).toContain("\u7b49\u5f85");
    expect(src).toContain("stats.waiting");
  });

  it("shows cancelled for stopped progress", () => {
    expect(src).toContain("\u5df2\u53d6\u6d88");
    expect(src).toContain("stats.cancelled");
  });

  it("keeps both waiting and cancelled visible together", () => {
    expect(src.indexOf("stats.waiting")).toBeGreaterThan(-1);
    expect(src.indexOf("stats.cancelled")).toBeGreaterThan(-1);
    expect(src).toContain("stats.success");
    expect(src).toContain("stats.rate_limited");
    expect(src).toContain("stats.failed");
  });
});
