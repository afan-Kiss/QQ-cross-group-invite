import { beforeEach, describe, expect, it, vi } from "vitest";

const loadMembersMock = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    loadMembers: (...args: unknown[]) => loadMembersMock(...args),
    mapLoadedMembers: (members: Array<{ qq: number; nickname: string; role: string; eligible?: boolean }>) =>
      members.map((m) => ({
        qq: m.qq,
        nickname: m.nickname,
        role: m.role || "member",
        status: m.eligible === false ? "filtered" : "waiting",
      })),
    getStatus: vi.fn(async () => ({
      running: false,
      status: "idle",
      task_id: "",
      total: 0,
      completed: 0,
      success: 0,
      rate_limited: 0,
      failed: 0,
      waiting: 0,
      inviting: 0,
      logs: [],
      rate_limit_list: [],
      failed_list: [],
      results: [],
      rate_series: [],
      members: [],
      current_qq: 0,
      current_nickname: "",
      message: "",
      error_message: "",
      started_at: 0,
      finished_at: 0,
      batch: {
        batchNumber: 0,
        batchTotal: 20,
        batchDone: 0,
        totalBatches: 0,
        currentNickname: "",
        currentQq: 0,
        intervalRemainingMs: 0,
        intervalMs: 0,
        nextInviteAt: 0,
      },
    })),
    stopInvite: vi.fn(),
    getConfig: vi.fn(),
    saveConfig: vi.fn(),
    startInvite: vi.fn(),
    listTasks: vi.fn(async () => []),
    clearLogs: vi.fn(),
    clearFailed: vi.fn(),
    clearRateLimits: vi.fn(),
  },
  ApiError: class ApiError extends Error {},
}));

vi.mock("@/store/useToastStore", () => ({ toast: vi.fn() }));
vi.mock("@/store/useLogStore", () => ({
  useLogStore: { getState: () => ({ pushFromLines: vi.fn(), setFromRaw: vi.fn(), clear: vi.fn() }) },
}));
vi.mock("@/store/useServiceStore", () => ({
  useServiceStore: {
    getState: () => ({ localService: "ready", napcatOnline: true, appSession: "s" }),
    setState: vi.fn(),
  },
}));
vi.mock("@/store/useSettingsStore", () => ({
  useSettingsStore: {
    getState: () => ({
      settings: { defaultBatchCount: "20", defaultIntervalMs: "1500", defaultFilterStaff: true },
    }),
  },
}));

import { useInviteStore } from "./useInviteStore";

describe("loadMembers race", () => {
  beforeEach(() => {
    loadMembersMock.mockReset();
    useInviteStore.setState({
      config: {
        target_group_id: "9",
        source_group_id: "A",
        batch_count: "20",
        interval_ms: "1500",
        filter_staff: true,
      },
      members: [],
      membersLoaded: false,
      selectedQqs: new Set(),
      loadingMembers: false,
    });
  });

  it("keeps B when A resolves after B", async () => {
    let resolveA: (v: unknown) => void = () => undefined;
    let resolveB: (v: unknown) => void = () => undefined;
    const pA = new Promise((r) => {
      resolveA = r;
    });
    const pB = new Promise((r) => {
      resolveB = r;
    });
    loadMembersMock.mockImplementationOnce(() => pA).mockImplementationOnce(() => pB);

    const store = useInviteStore.getState();
    const loadA = store.loadMembers();
    useInviteStore.getState().setConfig({ source_group_id: "B" });
    const loadB = useInviteStore.getState().loadMembers();

    resolveB({
      count: 1,
      eligible: 1,
      members: [{ qq: 200, nickname: "b", role: "member", eligible: true }],
    });
    await loadB;

    resolveA({
      count: 1,
      eligible: 1,
      members: [{ qq: 100, nickname: "a", role: "member", eligible: true }],
    });
    await loadA;

    const s = useInviteStore.getState();
    expect(s.config.source_group_id).toBe("B");
    expect(s.members.map((m) => m.qq)).toEqual([200]);
    expect([...s.selectedQqs]).toEqual([200]);
    expect(s.loadingMembers).toBe(false);
  });
});

describe("loadTasks clears stale currentTaskId", () => {
  it("sets null when no active task", async () => {
    const { api } = await import("@/lib/api");
    vi.mocked(api.listTasks).mockResolvedValueOnce([
      {
        id: "old",
        status: "completed",
        source_group_id: "1",
        target_group_id: "2",
        total: 1,
        success: 1,
        rate_limited: 0,
        failed: 0,
        started_at: 1,
      },
    ] as never);
    useInviteStore.setState({ currentTaskId: "old" });
    await useInviteStore.getState().loadTasks();
    expect(useInviteStore.getState().currentTaskId).toBeNull();
  });
});
