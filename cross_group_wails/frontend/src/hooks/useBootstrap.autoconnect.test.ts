import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";

describe("autoConnectOnStart boot-once", () => {
  it("useBootstrap decides once and does not depend on autoConnect in effect deps", () => {
    const src = fs.readFileSync(path.join(__dirname, "useBootstrap.ts"), "utf8");
    expect(src).toContain("bootDecisionDone");
    expect(src).toMatch(/}, \[ensureBackend, hydrated\]\)/);
    expect(src).not.toMatch(/}, \[ensureBackend, autoConnect, hydrated\]\)/);
  });
});
