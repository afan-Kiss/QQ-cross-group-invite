import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("dashboard copy and layout", () => {
  it("explains source vs target group and does not auto-load on type", () => {
    const text = readFileSync(resolve(__dirname, "ConfigPanel.tsx"), "utf8");
    expect(text).toContain("\u6765\u6e90\u7fa4\u53f7\uff08\u4ece\u54ea\u4e2a\u7fa4\u62c9\u4eba\uff09");
    expect(text).toContain("\u76ee\u6807\u7fa4\u53f7\uff08\u9080\u8bf7\u8fdb\u54ea\u4e2a\u7fa4\uff09");
    expect(text).toContain("\u52a0\u8f7d\u6210\u5458");
    expect(text).not.toContain("\u8fde\u63a5\u72b6\u6001");
  });

  it("puts connection status inside the run log card", () => {
    const text = readFileSync(resolve(__dirname, "LogPanel.tsx"), "utf8");
    expect(text).toContain("\u8fd0\u884c\u65e5\u5fd7");
    expect(text).toContain("\u672c\u5730\u670d\u52a1");
    expect(text).toContain("\u996d\u996d\u5b9a\u5236");
  });
});
