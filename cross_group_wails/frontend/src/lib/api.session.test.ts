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

  it("uses updated session after change", async () => {
    const store = useServiceStore as unknown as { __set: (s: string) => void };
    store.__set("old");
    await api.saveConfig({
      target_group_id: "1",
      source_group_id: "2",
      batch_count: "20",
      interval_ms: "1500",
      filter_staff: true,
    });
    store.__set("new");
    await api.saveConfig({
      target_group_id: "1",
      source_group_id: "2",
      batch_count: "20",
      interval_ms: "1500",
      filter_staff: true,
    });
    const h1 = fetchMock.mock.calls[0][1]?.headers as Record<string, string>;
    const h2 = fetchMock.mock.calls[1][1]?.headers as Record<string, string>;
    expect(h1["X-App-Session"]).toBe("old");
    expect(h2["X-App-Session"]).toBe("new");
  });
});
