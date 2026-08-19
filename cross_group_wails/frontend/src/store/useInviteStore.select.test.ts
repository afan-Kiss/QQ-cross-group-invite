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
        { qq: 4, nickname: "d", role: "member", status: "failed", failReason: "x", token: "old" },
        { qq: 5, nickname: "e", role: "member", status: "success" },
        { qq: 6, nickname: "f", role: "member", status: "rate_limited", failReason: "频繁" },
        { qq: 7, nickname: "g", role: "member", status: "cancelled", failReason: "已停止，未发送邀请" },
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

  it("requeueMember works for failed/rate_limited/cancelled but not success/filtered", () => {
    useInviteStore.getState().requeueMember(5);
    expect(vi.mocked(toast)).not.toHaveBeenCalled();
    expect(useInviteStore.getState().members.find((m) => m.qq === 5)?.status).toBe("success");
    useInviteStore.getState().requeueMember(3);
    expect(useInviteStore.getState().members.find((m) => m.qq === 3)?.status).toBe("filtered");
    expect(useInviteStore.getState().selectedQqs.has(3)).toBe(false);

    useInviteStore.getState().requeueMember(4);
    expect(useInviteStore.getState().members.find((m) => m.qq === 4)?.status).toBe("waiting");
    expect(useInviteStore.getState().members.find((m) => m.qq === 4)?.failReason).toBeUndefined();
    expect(useInviteStore.getState().selectedQqs.has(4)).toBe(true);

    useInviteStore.getState().requeueMember(6);
    expect(useInviteStore.getState().members.find((m) => m.qq === 6)?.status).toBe("waiting");
    expect(useInviteStore.getState().selectedQqs.has(6)).toBe(true);

    useInviteStore.getState().requeueMember(7);
    const cancelled = useInviteStore.getState().members.find((m) => m.qq === 7);
    expect(cancelled?.status).toBe("waiting");
    expect(cancelled?.failReason).toBeUndefined();
    expect(cancelled?.token).toBe("");
    expect(useInviteStore.getState().selectedQqs.has(7)).toBe(true);
  });

  it("cancelled cannot be selected until requeued to waiting", () => {
    useInviteStore.getState().selectQq(7);
    expect(useInviteStore.getState().selectedQqs.has(7)).toBe(false);
    useInviteStore.getState().requeueMember(7);
    expect(useInviteStore.getState().members.find((m) => m.qq === 7)?.status).toBe("waiting");
    expect(useInviteStore.getState().selectedQqs.has(7)).toBe(true);
  });

  it("source group change clears members", () => {
    useInviteStore.getState().setConfig({ source_group_id: "999" });
    const s = useInviteStore.getState();
    expect(s.membersLoaded).toBe(false);
    expect(s.members).toEqual([]);
    expect(s.selectedQqs.size).toBe(0);
  });
});
