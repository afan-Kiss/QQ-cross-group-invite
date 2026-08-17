import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("LogsPage export path", () => {
  it("calls wailsBridge.exportLogs", () => {
    const text = readFileSync(resolve(__dirname, "LogsPage.tsx"), "utf8");
    expect(text.includes("wailsBridge.exportLogs")).toBe(true);
    expect(text.includes("URL.createObjectURL")).toBe(false);
  });
});
