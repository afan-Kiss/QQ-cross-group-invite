import { beforeEach, describe, expect, it, vi } from "vitest";

const ensureMock = vi.fn();
const probeMock = vi.fn();

vi.mock("@/lib/wails-bridge", () => ({
  wailsBridge: {
    ensureBackend: (...a: unknown[]) => ensureMock(...a),
    probeHealth: (...a: unknown[]) => probeMock(...a),
  },
}));

import { useServiceStore } from "./useServiceStore";

describe("appSession cleared on bootstrap", () => {
  beforeEach(() => {
    ensureMock.mockReset();
    probeMock.mockReset();
    useServiceStore.setState({
      localService: "ready",
      message: "ok",
      startedByUs: true,
      napcatOnline: true,
      napcatMessage: "",
      bootstrapped: true,
      appSession: "sess-A",
      backendInstance: "cross-group-invite:1.0.0:1",
      backendPid: 1,
      backendVersion: "1.0.0",
      serviceEpoch: 1,
      lifecycleGeneration: 1,
      healthProbeGeneration: 1,
      refreshingNapcat: false,
    });
  });

  it("setBootstrapping clears appSession immediately", () => {
    useServiceStore.getState().setBootstrapping("booting");
    expect(useServiceStore.getState().appSession).toBe("");
    expect(useServiceStore.getState().serviceEpoch).toBeGreaterThan(1);
  });

  it("ensureBackend clears then sets new owned session", async () => {
    ensureMock.mockResolvedValueOnce({
      localService: "ready",
      message: "ok",
      startedByUs: true,
      napcatOnline: false,
      napcatMessage: "",
      appSession: "sess-B",
    });
    const p = useServiceStore.getState().ensureBackend();
    expect(useServiceStore.getState().appSession).toBe("");
    await p;
    expect(useServiceStore.getState().appSession).toBe("sess-B");
  });
});
