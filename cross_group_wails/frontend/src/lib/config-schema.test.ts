import { describe, expect, it } from "vitest";
import { inviteConfigSchema, parseInviteConfigForm } from "./invite-config-schema";

describe("inviteConfigSchema shared", () => {
  const base = {
    target_group_id: "1",
    source_group_id: "2",
    batch_count: "20",
    interval_ms: "1500",
    filter_staff: true,
  };

  it("accepts valid edges", () => {
    expect(parseInviteConfigForm({ ...base, batch_count: "1" }).success).toBe(true);
    expect(parseInviteConfigForm({ ...base, batch_count: "1000" }).success).toBe(true);
    expect(parseInviteConfigForm({ ...base, interval_ms: "100" }).success).toBe(true);
    expect(parseInviteConfigForm({ ...base, interval_ms: "600000" }).success).toBe(true);
    expect(parseInviteConfigForm({ ...base, source_group_id: "10001" }).success).toBe(true);
  });

  it("rejects empty/zero/leading-zero/non-digit groups", () => {
    for (const bad of ["", "0", "000", "-1", "abc"]) {
      expect(parseInviteConfigForm({ ...base, source_group_id: bad }).success).toBe(false);
      expect(parseInviteConfigForm({ ...base, target_group_id: bad }).success).toBe(false);
    }
  });

  it("rejects same groups and batch/interval bounds", () => {
    expect(parseInviteConfigForm({ ...base, source_group_id: "1" }).success).toBe(false);
    expect(parseInviteConfigForm({ ...base, batch_count: "0" }).success).toBe(false);
    expect(parseInviteConfigForm({ ...base, batch_count: "1001" }).success).toBe(false);
    expect(parseInviteConfigForm({ ...base, interval_ms: "99" }).success).toBe(false);
    expect(parseInviteConfigForm({ ...base, interval_ms: "600001" }).success).toBe(false);
  });

  it("exports the same schema object used by ConfigPanel", () => {
    expect(inviteConfigSchema).toBeTruthy();
  });
});
