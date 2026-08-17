import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  api: {},
  ApiError: class ApiError extends Error {},
  applyResultsToMembers: (m: unknown) => m,
}));
vi.mock("@/store/useToastStore", () => ({ toast: vi.fn() }));
vi.mock("@/store/useLogStore", () => ({
  useLogStore: { getState: () => ({ setFromRaw: vi.fn(), clear: vi.fn() }) },
}));
vi.mock("@/store/useServiceStore", () => ({
  useServiceStore: { getState: () => ({ localService: "ready", napcatOnline: true }), setState: vi.fn() },
}));
vi.mock("@/store/useSettingsStore", () => ({
  useSettingsStore: { getState: () => ({ settings: {} }) },
}));

import { toEpochMs } from "./utils";

describe("mapPersistedTask time via toEpochMs", () => {
  it("handles seconds", () => {
    expect(toEpochMs(1_700_000_000)).toBe(1_700_000_000_000);
  });
  it("handles milliseconds", () => {
    expect(toEpochMs(1_700_000_000_000)).toBe(1_700_000_000_000);
  });
  it("uses created_at ms when started_at missing", () => {
    const started_at = 0;
    const created_at = 1_700_000_000_000;
    // previous buggy formula multiplied created_at again
    const buggy =
      Number(started_at || created_at || 0) * (Number(started_at || 0) > 1e12 ? 1 : 1000);
    expect(buggy).toBe(1_700_000_000_000_000);
    expect(toEpochMs(started_at || created_at || 0)).toBe(1_700_000_000_000);
  });
});
