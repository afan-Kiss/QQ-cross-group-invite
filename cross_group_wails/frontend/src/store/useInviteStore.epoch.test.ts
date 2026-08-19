import { beforeEach, describe, expect, it, vi } from "vitest";

const getStatusMock = vi.fn();
let serviceEpoch = 1;

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getStatus: (...a: unknown[]) => getStatusMock(...a),
      listTasks: vi.fn(async () => []),
      saveConfig: vi.fn(),
      startInvite: vi.fn(),
      stopInvite: vi.fn(),
      loadMembers: vi.fn(),
      getConfig: vi.fn(),
      clearLogs: vi.fn(),
      clearFailed: vi.fn(),
      clearRateLimits: vi.fn(),
    },
  };
});

vi.mock("@/store/useToastStore", () => ({ toast: vi.fn() }));
vi.mock("@/store/useLogStore", () => ({
  useLogStore: { getState: () => ({ setFromRaw: vi.fn(), clear: vi.fn() }) },
}));
vi.mock("@/store/useServiceStore", () => ({
  useServiceStore: {
    getState: () => ({ localService: "ready", napcatOnline: true, appSession: "s", serviceEpoch }),
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

describe("serviceEpoch stale status discard", () => {
  beforeEach(() => {
    getStatusMock.mockReset();
    serviceEpoch = 1;
    useInviteStore.setState({
      config: {
        target_group_id: "9",
        source_group_id: "A",
        batch_count: "20",
        interval_ms: "1500",
        filter_staff: true,
      },
      members: [{ qq: 1, nickname: "u", role: "member", status: "waiting" }],
      membersRevision: 1,
      membersMutationGeneration: 1,
      memberResultTaskId: null,
      membersLoaded: true,
      inviting: false,
      invitePhase: "idle",
      currentTaskId: null,
      selectedQqs: new Set(),
      stats: {
        running: false,
        status: "idle",
        task_id: "",
        total: 0,
        completed: 0,
        success: 0,
        rate_limited: 0,
        failed: 0,
        cancelled: 0,
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
        message: "ready-mark",
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
      } as never,
      tasks: [],
    });
  });

  it("discards response after serviceEpoch changes", async () => {
    let resolveStatus: (v: unknown) => void = () => undefined;
    getStatusMock.mockImplementationOnce(
      () =>
        new Promise((r) => {
          resolveStatus = r;
        }),
    );
    const p = useInviteStore.getState().refreshStatus();
    serviceEpoch = 2;
    resolveStatus({
      running: true,
      status: "running",
      task_id: "stale",
      source_group_id: "A",
      target_group_id: "9",
      total: 1,
      completed: 0,
      success: 0,
      rate_limited: 0,
      failed: 0,
      cancelled: 0,
      waiting: 0,
      inviting: 1,
      logs: ["stale"],
      rate_limit_list: [],
      failed_list: [],
      results: [],
      rate_series: [],
      members: [],
      current_qq: 0,
      current_nickname: "",
      message: "should-not-apply",
      error_message: "",
      started_at: 0,
      finished_at: 0,
      napcat_online: true,
      napcat_message: "ok",
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
    });
    await p;
    expect(useInviteStore.getState().stats.message).toBe("ready-mark");
    expect(useInviteStore.getState().invitePhase).toBe("idle");
    expect(useInviteStore.getState().stats.task_id).toBe("");
  });
});
