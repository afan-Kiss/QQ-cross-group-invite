import { beforeEach, describe, expect, it, vi } from "vitest";

const ensureMock = vi.fn();
const probeMock = vi.fn();

vi.mock("@/lib/wails-bridge", () => ({
  wailsBridge: {
    ensureBackend: (...a: unknown[]) => ensureMock(...a),
    probeHealth: (...a: unknown[]) => probeMock(...a),
  },
}));

const refreshNapcatApi = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    refreshNapcat: (...a: unknown[]) => refreshNapcatApi(...a),
  },
}));

import { applyBootstrap, useServiceStore } from "./useServiceStore";

describe("service store request ordering + instance epoch", () => {
  beforeEach(() => {
    ensureMock.mockReset();
    probeMock.mockReset();
    refreshNapcatApi.mockReset();
    useServiceStore.setState({
      localService: "ready",
      message: "ok",
      startedByUs: true,
      napcatOnline: true,
      napcatMessage: "",
      bootstrapped: true,
      appSession: "sess-A",
      backendInstance: "cross-group-invite:1.0.0:1000",
      backendPid: 1000,
      backendVersion: "1.0.0",
      serviceEpoch: 1,
      lifecycleGeneration: 1,
      healthProbeGeneration: 1,
      refreshingNapcat: false,
    });
  });

  it("discards stale refreshHealth after ensureBackend", async () => {
    let resolveProbe: (v: unknown) => void = () => undefined;
    probeMock.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveProbe = resolve;
        }),
    );
    ensureMock.mockResolvedValueOnce({
      localService: "ready",
      message: "ok",
      startedByUs: true,
      napcatOnline: true,
      napcatMessage: "",
      appSession: "sess-B",
      backendInstance: "cross-group-invite:1.0.0:2000",
      backendPid: 2000,
      backendVersion: "1.0.0",
    });

    const refreshP = useServiceStore.getState().refreshHealth();
    const ensureP = useServiceStore.getState().ensureBackend();
    await ensureP;
    expect(useServiceStore.getState().appSession).toBe("sess-B");
    expect(useServiceStore.getState().startedByUs).toBe(true);

    resolveProbe({
      localService: "ready",
      message: "old",
      startedByUs: false,
      napcatOnline: false,
      napcatMessage: "",
      appSession: "",
      backendInstance: "cross-group-invite:1.0.0:1000",
      backendPid: 1000,
      backendVersion: "1.0.0",
    });
    await refreshP;
    expect(useServiceStore.getState().appSession).toBe("sess-B");
    expect(useServiceStore.getState().localService).toBe("ready");
    expect(useServiceStore.getState().startedByUs).toBe(true);
  });

  it("only latest ensureBackend wins", async () => {
    let resolveA: (v: unknown) => void = () => undefined;
    ensureMock
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveA = resolve;
          }),
      )
      .mockResolvedValueOnce({
        localService: "ready",
        message: "B",
        startedByUs: true,
        napcatOnline: true,
        napcatMessage: "",
        appSession: "sess-B",
        backendInstance: "cross-group-invite:1.0.0:2",
        backendPid: 2,
        backendVersion: "1.0.0",
      });

    const a = useServiceStore.getState().ensureBackend();
    const b = useServiceStore.getState().ensureBackend();
    await b;
    resolveA({
      localService: "ready",
      message: "A",
      startedByUs: true,
      napcatOnline: true,
      napcatMessage: "",
      appSession: "sess-A",
      backendInstance: "cross-group-invite:1.0.0:1",
      backendPid: 1,
      backendVersion: "1.0.0",
    });
    await a;
    expect(useServiceStore.getState().appSession).toBe("sess-B");
  });

  it("only latest refreshHealth probe wins", async () => {
    let resolveA: (v: unknown) => void = () => undefined;
    probeMock
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveA = resolve;
          }),
      )
      .mockResolvedValueOnce({
        localService: "ready",
        message: "B",
        startedByUs: true,
        napcatOnline: true,
        napcatMessage: "饭饭定制 online",
        appSession: "sess-B",
        backendInstance: "cross-group-invite:1.0.0:2000",
        backendPid: 2000,
        backendVersion: "1.0.0",
      });

    const a = useServiceStore.getState().refreshHealth();
    const b = useServiceStore.getState().refreshHealth();
    await b;
    expect(useServiceStore.getState().backendInstance).toBe("cross-group-invite:1.0.0:2000");
    resolveA({
      localService: "ready",
      message: "A",
      startedByUs: true,
      napcatOnline: false,
      napcatMessage: "old",
      appSession: "sess-A",
      backendInstance: "cross-group-invite:1.0.0:1000",
      backendPid: 1000,
      backendVersion: "1.0.0",
    });
    await a;
    expect(useServiceStore.getState().backendInstance).toBe("cross-group-invite:1.0.0:2000");
    expect(useServiceStore.getState().appSession).toBe("sess-B");
  });

  it("refreshNapcat updates store from API", async () => {
    refreshNapcatApi.mockResolvedValueOnce({
      napcat_online: true,
      napcat_message: "饭饭定制 online",
    });
    await useServiceStore.getState().refreshNapcat();
    expect(useServiceStore.getState().napcatOnline).toBe(true);
    expect(useServiceStore.getState().napcatMessage).toBe("饭饭定制 online");
    expect(useServiceStore.getState().refreshingNapcat).toBe(false);
  });

  it("bumps serviceEpoch when external backendInstance PID changes", () => {
    const prev = {
      localService: "ready",
      appSession: "",
      backendInstance: "cross-group-invite:1.0.0:1000",
      serviceEpoch: 5,
    };
    const next = applyBootstrap(prev, {
      localService: "ready",
      message: "ok",
      startedByUs: false,
      napcatOnline: true,
      napcatMessage: "",
      appSession: "",
      backendInstance: "cross-group-invite:1.0.0:2000",
      backendPid: 2000,
      backendVersion: "1.0.0",
    });
    expect(next.serviceEpoch).toBe(6);
    expect(next.backendInstance).toBe("cross-group-invite:1.0.0:2000");
  });
});
