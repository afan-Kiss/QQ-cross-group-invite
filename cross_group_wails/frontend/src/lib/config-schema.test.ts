import { describe, expect, it } from "vitest";
import {
  inviteConfigSchema,
  parseInviteConfigForm,
  parseInviteDefaults,
  parseLogSettings,
  validateInviteBatchInterval,
} from "./invite-config-schema";

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

  it("settings defaults share the same batch/interval bounds", () => {
    expect(parseInviteDefaults({ defaultBatchCount: "1", defaultIntervalMs: "100" }).success).toBe(true);
    expect(parseInviteDefaults({ defaultBatchCount: "1000", defaultIntervalMs: "600000" }).success).toBe(true);
    expect(parseInviteDefaults({ defaultBatchCount: "0", defaultIntervalMs: "1500" }).success).toBe(false);
    expect(parseInviteDefaults({ defaultBatchCount: "1001", defaultIntervalMs: "1500" }).success).toBe(false);
    expect(parseInviteDefaults({ defaultBatchCount: "abc", defaultIntervalMs: "1500" }).success).toBe(false);
    expect(parseInviteDefaults({ defaultBatchCount: "20", defaultIntervalMs: "99" }).success).toBe(false);
    expect(parseInviteDefaults({ defaultBatchCount: "20", defaultIntervalMs: "600001" }).success).toBe(false);
    expect(parseInviteDefaults({ defaultBatchCount: "20", defaultIntervalMs: "abc" }).success).toBe(false);
  });

  it("validateInviteBatchInterval rejects silent fallbacks", () => {
    expect(validateInviteBatchInterval("0", "1500").ok).toBe(false);
    expect(validateInviteBatchInterval("20", "1").ok).toBe(false);
    const ok = validateInviteBatchInterval("20", "1500");
    expect(ok.ok).toBe(true);
    if (ok.ok) {
      expect(ok.batch).toBe(20);
      expect(ok.interval).toBe(1500);
    }
  });

  it("log settings share bounds used by SettingsPage", () => {
    expect(
      parseLogSettings({
        logLevel: "INFO",
        maxLogFileSize: "1",
        logRetentionDays: "1",
        autoCleanLogs: true,
      }).success,
    ).toBe(true);
    expect(
      parseLogSettings({
        logLevel: "WARN",
        maxLogFileSize: "abc",
        logRetentionDays: "7",
        autoCleanLogs: true,
      }).success,
    ).toBe(false);
    expect(
      parseLogSettings({
        logLevel: "ERROR",
        maxLogFileSize: "5",
        logRetentionDays: "3651",
        autoCleanLogs: false,
      }).success,
    ).toBe(false);
  });
});
