import { beforeEach, describe, expect, it, vi } from "vitest";

const fetchMock = vi.fn();
vi.stubGlobal("fetch", fetchMock);

vi.mock("@/store/useServiceStore", () => {
  let appSession = "";
  return {
    useServiceStore: {
      getState: () => ({ appSession }),
      setState: (p: { appSession?: string }) => {
        if (p.appSession !== undefined) appSession = p.appSession;
      },
      __set: (s: string) => {
        appSession = s;
      },
    },
  };
});

import { api } from "@/lib/api";
import { useServiceStore } from "@/store/useServiceStore";

describe("api request X-App-Session", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true }),
    });
    (useServiceStore as unknown as { __set: (s: string) => void }).__set("");
  });

  it("adds header when appSession present for mutating calls", async () => {
    (useServiceStore as unknown as { __set: (s: string) => void }).__set("sess-A");
    await api.saveConfig({
      target_group_id: "1",
      source_group_id: "2",
      batch_count: "20",
      interval_ms: "1500",
      filter_staff: true,
    });
    await api.loadMembers({ source_group_id: "2", filter_staff: true });
    await api.startInvite({
      target_group_id: "1",
      source_group_id: "2",
      batch_count: 20,
      interval_ms: 1500,
      filter_staff: true,
      qq_list: [1],
    });
    await api.stopInvite("tid");
    await api.clearFailed();
    await api.clearRateLimits();
    await api.clearLogs();
    await api.testConnection();
    const posts = fetchMock.mock.calls.filter((c) => String(c[1]?.method).toUpperCase() === "POST");
    expect(posts.length).toBeGreaterThanOrEqual(7);
    for (const call of posts) {
      const headers = call[1]?.headers as Record<string, string>;
      expect(headers["X-App-Session"]).toBe("sess-A");
    }
  });

  it("omits header when appSession empty", async () => {
    (useServiceStore as unknown as { __set: (s: string) => void }).__set("");
    await api.saveConfig({
      target_group_id: "1",
      source_group_id: "2",
      batch_count: "20",
      interval_ms: "1500",
      filter_staff: true,
    });
    const headers = fetchMock.mock.calls[0][1]?.headers as Record<string, string>;
    expect(headers["X-App-Session"]).toBeUndefined();
  });

  it("adds header for GET business calls when appSession present", async () => {
    (useServiceStore as unknown as { __set: (s: string) => void }).__set("sess-A");
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        ok: true,
        target_group_id: "1",
        source_group_id: "2",
        batch_count: "20",
        interval_ms: "1500",
        filter_staff: true,
        tasks: [],
        running: false,
      }),
    });
    await api.getConfig();
    await api.getStatus();
    await api.listTasks();
    for (const call of fetchMock.mock.calls) {
      const headers = call[1]?.headers as Record<string, string>;
      expect(headers["X-App-Session"]).toBe("sess-A");
    }
  });
});
