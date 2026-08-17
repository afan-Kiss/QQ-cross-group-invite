import { beforeEach, describe, expect, it, vi } from "vitest";

const saveConfigMock = vi.fn();
const startInviteApiMock = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    stopInvite: vi.fn(),
    getConfig: vi.fn(),
    saveConfig: (...a: unknown[]) => saveConfigMock(...a),
    loadMembers: vi.fn(),
    startInvite: (...a: unknown[]) => startInviteApiMock(...a),
    getStatus: vi.fn(),
    listTasks: vi.fn(),
    clearLogs: vi.fn(),
    clearFailed: vi.fn(),
    clearRateLimits: vi.fn(),
    mapLoadedMembers: vi.fn(),
  },
  ApiError: class ApiError extends Error {},
  applyResultsToMembers: (m: unknown) => m,
}));

vi.mock("@/store/useToastStore", () => ({ toast: vi.fn() }));
vi.mock("@/store/useLogStore", () => ({
  useLogStore: { getState: () => ({ pushFromLines: vi.fn() }) },
}));
vi.mock("@/store/useServiceStore", () => ({
  useServiceStore: {
    getState: () => ({ localService: "ready", napcatOnline: true, appSession: "s" }),
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

describe("startInvite validates before save", () => {
  beforeEach(() => {
    saveConfigMock.mockReset();
    startInviteApiMock.mockReset();
    vi.mocked(toast).mockClear();
    useInviteStore.setState({
      invitePhase: "idle",
      inviting: false,
      membersLoaded: true,
      members: [{ qq: 10001, nickname: "a", role: "member", status: "waiting" }],
      selectedQqs: new Set([10001]),
      config: {
        target_group_id: "200",
        source_group_id: "100",
        batch_count: "0",
        interval_ms: "1500",
        filter_staff: true,
      },
    });
  });

  it("invalid batch does not call saveConfig or startInvite", async () => {
    await useInviteStore.getState().startInvite();
    expect(saveConfigMock).not.toHaveBeenCalled();
    expect(startInviteApiMock).not.toHaveBeenCalled();
    expect(useInviteStore.getState().invitePhase).toBe("idle");
  });

  it("invalid interval does not call saveConfig or startInvite", async () => {
    useInviteStore.setState({
      config: {
        target_group_id: "200",
        source_group_id: "100",
        batch_count: "10",
        interval_ms: "50",
        filter_staff: true,
      },
    });
    await useInviteStore.getState().startInvite();
    expect(saveConfigMock).not.toHaveBeenCalled();
    expect(startInviteApiMock).not.toHaveBeenCalled();
    expect(useInviteStore.getState().invitePhase).toBe("idle");
  });
});

describe("selection only waiting", () => {
  beforeEach(() => {
    useInviteStore.setState({
      members: [
        { qq: 1, nickname: "a", role: "member", status: "waiting" },
        { qq: 2, nickname: "b", role: "member", status: "failed" },
        { qq: 3, nickname: "c", role: "member", status: "rate_limited" },
      ],
      selectedQqs: new Set(),
      membersLoaded: true,
    });
  });

  it("failed cannot direct select", () => {
    useInviteStore.getState().selectQq(2);
    expect(useInviteStore.getState().selectedQqs.has(2)).toBe(false);
  });

  it("rate_limited cannot direct toggle", () => {
    useInviteStore.getState().toggleSelect(3);
    expect(useInviteStore.getState().selectedQqs.has(3)).toBe(false);
  });

  it("requeue then selectable", () => {
    useInviteStore.getState().requeueMember(2);
    expect(useInviteStore.getState().members.find((m) => m.qq === 2)?.status).toBe("waiting");
    expect(useInviteStore.getState().selectedQqs.has(2)).toBe(true);
  });
});
