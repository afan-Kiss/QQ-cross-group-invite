import { beforeEach, describe, expect, it, vi } from "vitest";

const getStatusMock = vi.fn();
const startInviteMock = vi.fn();
const stopInviteMock = vi.fn();
const saveConfigMock = vi.fn(async () => undefined);
const loadMembersMock = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getStatus: (...args: unknown[]) => getStatusMock(...args),
      startInvite: (...args: unknown[]) => startInviteMock(...args),
      stopInvite: (...args: unknown[]) => stopInviteMock(...args),
      saveConfig: (...args: unknown[]) => saveConfigMock(...args),
      loadMembers: (...args: unknown[]) => loadMembersMock(...args),
      listTasks: vi.fn(async () => []),
      clearLogs: vi.fn(),
      clearFailed: vi.fn(),
      clearRateLimits: vi.fn(),
      getConfig: vi.fn(),
    },
  };
});

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

function baseStatus(over: Record<string, unknown> = {}) {
  return {
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
    ...over,
  };
}

describe("member result ownership", () => {
  beforeEach(() => {
    getStatusMock.mockReset();
    startInviteMock.mockReset();
    stopInviteMock.mockReset();
    loadMembersMock.mockReset();
    useInviteStore.setState({
      config: {
        target_group_id: "9",
        source_group_id: "A",
        batch_count: "20",
        interval_ms: "1500",
        filter_staff: true,
      },
      members: [{ qq: 10001, nickname: "u", role: "member", status: "waiting" }],
      membersRevision: 1,
      memberResultTaskId: null,
      membersLoaded: true,
      selectedQqs: new Set([10001]),
      inviting: false,
      invitePhase: "idle",
      currentTaskId: null,
      stats: baseStatus({ task_id: "task-old" }) as never,
      tasks: [],
    });
  });

  it("does not apply stale task-old results when memberResultTaskId is null", async () => {
    getStatusMock.mockResolvedValueOnce(
      baseStatus({
        task_id: "task-old",
        status: "completed",
        results: [
          {
            qq: 10001,
            nickname: "u",
            status: "success",
            reason: "",
            started_at: 1,
            finished_at: 2,
            duration_ms: 1,
          },
        ],
      }),
    );
    await useInviteStore.getState().refreshStatus();
    expect(useInviteStore.getState().members[0].status).toBe("waiting");
  });

  it("applies results when task_id matches memberResultTaskId", async () => {
    useInviteStore.setState({ memberResultTaskId: "task-new" });
    getStatusMock.mockResolvedValueOnce(
      baseStatus({
        task_id: "task-new",
        status: "running",
        running: true,
        results: [
          {
            qq: 10001,
            nickname: "u",
            status: "success",
            reason: "",
            started_at: 1,
            finished_at: 2,
            duration_ms: 1,
          },
        ],
      }),
    );
    await useInviteStore.getState().refreshStatus();
    expect(useInviteStore.getState().members[0].status).toBe("success");
  });

  it("ignores results when task_id mismatches memberResultTaskId", async () => {
    useInviteStore.setState({ memberResultTaskId: "task-new" });
    getStatusMock.mockResolvedValueOnce(
      baseStatus({
        task_id: "task-old",
        results: [
          {
            qq: 10001,
            nickname: "u",
            status: "failed",
            reason: "x",
            started_at: 1,
            finished_at: 2,
            duration_ms: 1,
          },
        ],
      }),
    );
    await useInviteStore.getState().refreshStatus();
    expect(useInviteStore.getState().members[0].status).toBe("waiting");
  });

  it("does not restore members from in-flight refresh after source group change", async () => {
    let resolveStatus: (v: unknown) => void = () => undefined;
    const pending = new Promise((r) => {
      resolveStatus = r;
    });
    getStatusMock.mockImplementationOnce(() => pending);

    const refreshP = useInviteStore.getState().refreshStatus();
    useInviteStore.getState().setConfig({ source_group_id: "B" });
    expect(useInviteStore.getState().members).toEqual([]);
    expect(useInviteStore.getState().config.source_group_id).toBe("B");

    resolveStatus(
      baseStatus({
        task_id: "task-old",
        members: [{ qq: 10001, nickname: "a", role: "member", status: "success" }],
        results: [
          {
            qq: 10001,
            nickname: "a",
            status: "success",
            reason: "",
            started_at: 1,
            finished_at: 2,
            duration_ms: 1,
          },
        ],
      }),
    );
    await refreshP;

    const s = useInviteStore.getState();
    expect(s.config.source_group_id).toBe("B");
    expect(s.members).toEqual([]);
  });
});

describe("start/stop phase task-id race", () => {
  beforeEach(() => {
    getStatusMock.mockReset();
    startInviteMock.mockReset();
    stopInviteMock.mockReset();
    getStatusMock.mockResolvedValue(baseStatus());
    useInviteStore.setState({
      config: {
        target_group_id: "9",
        source_group_id: "A",
        batch_count: "20",
        interval_ms: "1500",
        filter_staff: true,
      },
      members: [{ qq: 10001, nickname: "u", role: "member", status: "waiting" }],
      membersLoaded: true,
      selectedQqs: new Set([10001]),
      inviting: false,
      invitePhase: "idle",
      memberResultTaskId: null,
      currentTaskId: "old-task",
      stats: baseStatus({ task_id: "old-task" }) as never,
      tasks: [],
    });
  });

  it("does not stop with old-task while starting", async () => {
    let resolveStart: (v: unknown) => void = () => undefined;
    startInviteMock.mockImplementationOnce(
      () =>
        new Promise((r) => {
          resolveStart = r;
        }),
    );
    const startP = useInviteStore.getState().startInvite();
    expect(useInviteStore.getState().invitePhase).toBe("starting");
    await useInviteStore.getState().stopInvite();
    expect(stopInviteMock).not.toHaveBeenCalled();
    resolveStart({ task_id: "task-new" });
    await startP;
    expect(useInviteStore.getState().invitePhase).toBe("running");
    expect(useInviteStore.getState().memberResultTaskId).toBe("task-new");
    await useInviteStore.getState().stopInvite();
    expect(stopInviteMock).toHaveBeenCalledWith("task-new");
  });

  it("returns idle when start API fails", async () => {
    startInviteMock.mockRejectedValueOnce(new Error("boom"));
    await useInviteStore.getState().startInvite();
    expect(useInviteStore.getState().invitePhase).toBe("idle");
    expect(useInviteStore.getState().inviting).toBe(false);
  });

  it("blocks start while stopping", async () => {
    useInviteStore.setState({
      invitePhase: "stopping",
      inviting: true,
      memberResultTaskId: "task-new",
      currentTaskId: "task-new",
    });
    await useInviteStore.getState().startInvite();
    expect(startInviteMock).not.toHaveBeenCalled();
  });
});
