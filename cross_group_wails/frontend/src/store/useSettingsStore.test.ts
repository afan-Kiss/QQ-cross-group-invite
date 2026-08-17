import { beforeEach, describe, expect, it, vi } from "vitest";

const store = new Map<string, string>();
const matchMedia = (query: string) => ({
  matches: false,
  media: query,
  addEventListener: () => undefined,
  removeEventListener: () => undefined,
  addListener: () => undefined,
  removeListener: () => undefined,
  dispatchEvent: () => false,
  onchange: null,
});

vi.stubGlobal("localStorage", {
  getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
  setItem: (k: string, v: string) => {
    store.set(k, String(v));
  },
  removeItem: (k: string) => {
    store.delete(k);
  },
  clear: () => store.clear(),
});

vi.stubGlobal("window", { matchMedia });
vi.stubGlobal("matchMedia", matchMedia);
vi.stubGlobal("document", {
  documentElement: {
    style: { fontSize: "" },
    classList: { toggle: () => undefined },
  },
});

import { persistSettings, useSettingsStore } from "./useSettingsStore";

describe("persistSettings", () => {
  beforeEach(() => {
    store.clear();
    useSettingsStore.setState({
      settings: {
        ...useSettingsStore.getState().settings,
        napcatWebuiToken: "secret-token",
        autoConnectOnStart: false,
      },
      hydrated: false,
    });
  });

  it("does not persist napcat token", () => {
    persistSettings(useSettingsStore.getState().settings);
    const raw = localStorage.getItem("qq-cross-group-settings");
    expect(raw).toBeTruthy();
    expect(raw!.includes("secret-token")).toBe(false);
    expect(JSON.parse(raw!).napcatWebuiToken).toBe("");
  });

  it("load strips legacy token and marks hydrated", () => {
    localStorage.setItem(
      "qq-cross-group-settings",
      JSON.stringify({ napcatWebuiToken: "legacy", autoConnectOnStart: false }),
    );
    useSettingsStore.getState().load();
    expect(useSettingsStore.getState().hydrated).toBe(true);
    expect(useSettingsStore.getState().settings.napcatWebuiToken).toBe("");
    expect(useSettingsStore.getState().settings.autoConnectOnStart).toBe(false);
  });
});
