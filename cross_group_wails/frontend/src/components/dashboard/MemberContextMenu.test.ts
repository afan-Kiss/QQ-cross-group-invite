import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";

describe("MemberContextMenu queue rules", () => {
  const src = fs.readFileSync(
    path.join(__dirname, "MemberContextMenu.tsx"),
    "utf8",
  );

  it("canQueue only allows waiting", () => {
    expect(src).toContain('const canQueue = member.status === "waiting";');
    expect(src).not.toMatch(
      /canQueue\s*=\s*member\.status === "waiting"\s*\|\|\s*member\.status === "failed"/,
    );
  });

  it("requeue remains available for failed/rate_limited", () => {
    expect(src).toContain("\u91cd\u65b0\u9080\u8bf7");
    expect(src).toContain(
      'disabled: !(member.status === "failed" || member.status === "rate_limited")',
    );
    expect(src).toContain("requeueMember(member.qq)");
  });

  it("join queue uses selectQq and is gated by canQueue", () => {
    expect(src).toContain("disabled: !canQueue");
    expect(src).toContain("selectQq(member.qq)");
  });
});
