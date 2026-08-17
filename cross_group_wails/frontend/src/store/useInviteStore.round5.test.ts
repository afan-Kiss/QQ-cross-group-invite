import { beforeEach, describe, expect, it, vi } from "vitest";

const getStatusMock = vi.fn();
const getConfigMock = vi.fn();
const startInviteMock = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getStatus: (...a: unknown[]) => getStatusMock(...a),
      getConfig: (...a: unknown[]) => getConfigMock(...a),
      startInvite: (...a: unknown[]) => startInviteMock(...a),
      saveConfig: vi.fn(async () => undefined),
      loadMembers: vi.fn(),
      stopInvite: vi.fn(),
      listTasks: vi.fn(async () => []),
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
    source_group_id: "A",
    target_group_id: "9",
    total: 1,
    completed: 1,
    success: 0,
    rate_limited: 0,
    failed: 1,
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

describe("requeue vs stale results", () => {
  beforeEach(() => {
    getStatusMock.mockReset();
    useInviteStore.setState({
      config: {
        target_group_id: "9",
        source_group_id: "A",
        batch_count: "20",
        interval_ms: "1500",
        filter_staff: true,
      },
      members: [{ qq: 10001, nickname: "u", role: "member", status: "failed" }],
      membersRevision: 1,
      membersMutationGeneration: 1,
      memberResultTaskId: "task-old",
      membersLoaded: true,
      selectedQqs: new Set(),
      inviting: false,
      invitePhase: "idle",
      currentTaskId: "task-old",
      stats: baseStatus({ task_id: "task-old", status: "completed" }) as never,
      tasks: [],
    });
  });

  it("keeps waiting after requeue even if old results return", async () => {
    useInviteStore.getState().requeueMember(10001);
    expect(useInviteStore.getState().members[0].status).toBe("waiting");
    expect(useInviteStore.getState().memberResultTaskId).toBeNull();
    expect([...useInviteStore.getState().selectedQqs]).toEqual([10001]);

    getStatusMock.mockResolvedValueOnce(
      baseStatus({
        task_id: "task-old",
        status: "completed",
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

  it("in-flight refresh cannot overwrite requeue", async () => {
    let resolveStatus: (v: unknown) => void = () => undefined;
    getStatusMock.mockImplementationOnce(
      () =>
        new Promise((r) => {
          resolveStatus = r;
        }),
    );
    const p = useInviteStore.getState().refreshStatus();
    useInviteStore.getState().requeueMember(10001);
    resolveStatus(
      baseStatus({
        task_id: "task-old",
        status: "completed",
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
    await p;
    expect(useInviteStore.getState().members[0].status).toBe("waiting");
  });

  it("strips success from selectedQqs after terminal owned results", async () => {
    useInviteStore.setState({
      members: [
        { qq: 10001, nickname: "u", role: "member", status: "waiting" },
        { qq: 10002, nickname: "v", role: "member", status: "waiting" },
      ],
      selectedQqs: new Set([10001, 10002]),
      memberResultTaskId: "task-new",
      membersMutationGeneration: 2,
    });
    getStatusMock.mockResolvedValueOnce(
      baseStatus({
        task_id: "task-new",
        status: "completed",
        running: false,
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
          {
            qq: 10002,
            nickname: "v",
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
    const s = useInviteStore.getState();
    expect(s.members.find((m) => m.qq === 10001)?.status).toBe("success");
    expect(s.selectedQqs.has(10001)).toBe(false);
    expect(s.selectedQqs.has(10002)).toBe(false);
  });
});

describe("status response ordering", () => {
  beforeEach(() => {
    getStatusMock.mockReset();
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
      memberResultTaskId: "t1",
      membersLoaded: true,
      inviting: true,
      invitePhase: "running",
      currentTaskId: "t1",
      selectedQqs: new Set([1]),
      stats: baseStatus({ task_id: "t1", running: true, status: "running" }) as never,
      tasks: [],
    });
  });

  it("ignores older running after newer stopped", async () => {
    let resolveR1: (v: unknown) => void = () => undefined;
    let resolveR2: (v: unknown) => void = () => undefined;
    getStatusMock
      .mockImplementationOnce(
        () =>
          new Promise((r) => {
            resolveR1 = r;
          }),
      )
      .mockImplementationOnce(
        () =>
          new Promise((r) => {
            resolveR2 = r;
          }),
      );

    const p1 = useInviteStore.getState().refreshStatus();
    const p2 = useInviteStore.getState().refreshStatus();
    resolveR2(
      baseStatus({
        task_id: "t1",
        running: false,
        status: "stopped",
        source_group_id: "A",
        target_group_id: "9",
      }),
    );
    await p2;
    expect(useInviteStore.getState().invitePhase).toBe("idle");
    resolveR1(
      baseStatus({
        task_id: "t1",
        running: true,
        status: "running",
        source_group_id: "A",
        target_group_id: "9",
      }),
    );
    await p1;
    expect(useInviteStore.getState().invitePhase).toBe("idle");
    expect(useInviteStore.getState().inviting).toBe(false);
  });
});

describe("loadConfig invalidates members", () => {
  it("clears members when remote source changes", async () => {
    getConfigMock.mockResolvedValueOnce({
      target_group_id: "9",
      source_group_id: "B",
      batch_count: "20",
      interval_ms: "1500",
      filter_staff: true,
    });
    useInviteStore.setState({
      config: {
        target_group_id: "9",
        source_group_id: "A",
        batch_count: "20",
        interval_ms: "1500",
        filter_staff: true,
      },
      members: [{ qq: 100, nickname: "a", role: "member", status: "waiting" }],
      membersLoaded: true,
      memberResultTaskId: "t",
      selectedQqs: new Set([100]),
      membersRevision: 3,
      membersMutationGeneration: 3,
    });
    await useInviteStore.getState().loadConfig();
    const s = useInviteStore.getState();
    expect(s.config.source_group_id).toBe("B");
    expect(s.members).toEqual([]);
    expect(s.membersLoaded).toBe(false);
    expect(s.memberResultTaskId).toBeNull();
    expect(s.selectedQqs.size).toBe(0);
  });
});

describe("active task recovery", () => {
  it("adopts matching running task after start response loss", async () => {
    startInviteMock.mockRejectedValueOnce(new Error("network"));
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
      invitePhase: "idle",
      memberResultTaskId: null,
      membersRevision: 1,
      membersMutationGeneration: 1,
    });
    await useInviteStore.getState().startInvite();
    expect(useInviteStore.getState().invitePhase).toBe("idle");

    getStatusMock.mockResolvedValueOnce(
      baseStatus({
        task_id: "task-new",
        running: true,
        status: "running",
        source_group_id: "A",
        target_group_id: "9",
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
    const s = useInviteStore.getState();
    expect(s.memberResultTaskId).toBe("task-new");
    expect(s.invitePhase).toBe("running");
    expect(s.members[0].status).toBe("success");
  });

  it("does not adopt mismatched source group results", async () => {
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
      memberResultTaskId: null,
      membersRevision: 1,
      membersMutationGeneration: 1,
      invitePhase: "idle",
    });
    getStatusMock.mockResolvedValueOnce(
      baseStatus({
        task_id: "other",
        running: true,
        status: "running",
        source_group_id: "B",
        target_group_id: "9",
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
    expect(useInviteStore.getState().memberResultTaskId).toBeNull();
    expect(useInviteStore.getState().members[0].status).toBe("waiting");
  });
});
