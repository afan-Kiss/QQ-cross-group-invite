import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const files = [
  "pages/TasksPage.tsx",
  "components/dashboard/MemberDetailDrawer.tsx",
  "pages/RateLimitPage.tsx",
  "pages/FailedPage.tsx",
  "pages/LogsPage.tsx",
];

describe("critical pages have real Chinese labels", () => {
  for (const rel of files) {
    it(rel, () => {
      const text = readFileSync(resolve(__dirname, "..", rel), "utf8");
      expect((text.match(/\?{3,}/g) || []).length).toBe(0);
      expect(/[\u4e00-\u9fff]/.test(text)).toBe(true);
    });
  }
});
