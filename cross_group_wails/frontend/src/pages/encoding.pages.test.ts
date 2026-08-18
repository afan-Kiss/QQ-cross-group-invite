import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const files = [
  "pages/TasksPage.tsx",
  "pages/TaskDetailPage.tsx",
  "components/dashboard/MemberDetailDrawer.tsx",
  "pages/RateLimitPage.tsx",
  "pages/FailedPage.tsx",
  "pages/LogsPage.tsx",
  "pages/SettingsPage.tsx",
];

describe("critical pages have real Chinese labels", () => {
  for (const rel of files) {
    it(rel, () => {
      const text = readFileSync(resolve(__dirname, "..", rel), "utf8");
      expect((text.match(/\?{3,}/g) || []).length).toBe(0);
      expect(/[\u4e00-\u9fff]/.test(text)).toBe(true);
    });
  }

  it("settings log level dropdown is Chinese", () => {
    const text = readFileSync(resolve(__dirname, "..", "pages", "SettingsPage.tsx"), "utf8");
    expect(text).toContain("LOG_LEVEL_LABELS");
  });

  it("FailedPage and RateLimitPage can open member drawer from layout", () => {
    const layout = readFileSync(resolve(__dirname, "..", "layouts", "MainLayout.tsx"), "utf8");
    expect(layout).toContain("MemberDetailDrawer");
    const table = readFileSync(resolve(__dirname, "..", "components", "dashboard", "MemberTable.tsx"), "utf8");
    expect(table).not.toContain("MemberDetailDrawer");
  });
});
