import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  api: {
    stopInvite: vi.fn(),
    getConfig: vi.fn(),
    saveConfig: vi.fn(),
    loadMembers: vi.fn(),
    startInvite: vi.fn(),
    getStatus: vi.fn(),
    listTasks: vi.fn(),
    clearLogs: vi.fn(),
    clearFailed: vi.fn(),
    clearRateLimits: vi.fn(),
    mapLoadedMembers: vi.fn(),
  },
  ApiError: class ApiError extends Error {},
}));

vi.mock("@/store/useToastStore", () => ({
  toast: vi.fn(),
}));

vi.mock("@/store/useLogStore", () => ({
  useLogStore: { getState: () => ({ pushFromLines: vi.fn() }) },
}));

vi.mock("@/store/useServiceStore", () => ({
  useServiceStore: {
    getState: () => ({ localService: "ready", napcatOnline: true }),
  },
}));

vi.mock("@/store/useSettingsStore", () => ({
  useSettingsStore: {
    getState: () => ({
      settings: {
        defaultBatchCount: "20",
        defaultIntervalMs: "1500",
        defaultFilterStaff: true,
      },
    }),
  },
}));

import { useInviteStore } from "./useInviteStore";
import { toast } from "@/store/useToastStore";

describe("selection helpers", () => {
  beforeEach(() => {
    useInviteStore.setState({
      members: [
        { qq: 1, nickname: "a", role: "member", status: "waiting" },
        { qq: 2, nickname: "b", role: "member", status: "waiting" },
        { qq: 3, nickname: "c", role: "member", status: "filtered" },
        { qq: 4, nickname: "d", role: "member", status: "failed" },
        { qq: 5, nickname: "e", role: "member", status: "success" },
      ],
      selectedQqs: new Set([1]),
      membersLoaded: true,
      config: {
        target_group_id: "1",
        source_group_id: "2",
        batch_count: "20",
        interval_ms: "1500",
        filter_staff: true,
      },
    });
    vi.mocked(toast).mockClear();
  });

  it("toggleSelectAll only affects provided page qqs", () => {
    useInviteStore.getState().toggleSelectAll([2]);
    expect([...useInviteStore.getState().selectedQqs].sort()).toEqual([1, 2]);
    useInviteStore.getState().toggleSelectAll([2]);
    expect([...useInviteStore.getState().selectedQqs]).toEqual([1]);
  });

  it("selectQq rejects filtered/success", () => {
    useInviteStore.getState().selectQq(3);
    useInviteStore.getState().selectQq(5);
    expect(useInviteStore.getState().selectedQqs.has(3)).toBe(false);
    expect(useInviteStore.getState().selectedQqs.has(5)).toBe(false);
  });

  it("requeueMember only works for failed/rate_limited", () => {
    useInviteStore.getState().requeueMember(5);
    expect(vi.mocked(toast)).not.toHaveBeenCalled();
    expect(useInviteStore.getState().members.find((m) => m.qq === 5)?.status).toBe("success");
    useInviteStore.getState().requeueMember(4);
    expect(useInviteStore.getState().members.find((m) => m.qq === 4)?.status).toBe("waiting");
    expect(useInviteStore.getState().selectedQqs.has(4)).toBe(true);
  });

  it("source group change clears members", () => {
    useInviteStore.getState().setConfig({ source_group_id: "999" });
    const s = useInviteStore.getState();
    expect(s.membersLoaded).toBe(false);
    expect(s.members).toEqual([]);
    expect(s.selectedQqs.size).toBe(0);
  });
});
