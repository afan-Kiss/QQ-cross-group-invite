import { useEffect, useRef } from "react";
import { useServiceStore } from "@/store/useServiceStore";
import { useInviteStore } from "@/store/useInviteStore";
import { useSettingsStore } from "@/store/useSettingsStore";

export function useBootstrap() {
  const ensureBackend = useServiceStore((s) => s.ensureBackend);
  const refreshHealth = useServiceStore((s) => s.refreshHealth);
  const bootstrapped = useServiceStore((s) => s.bootstrapped);
  const localService = useServiceStore((s) => s.localService);
  const loadConfig = useInviteStore((s) => s.loadConfig);
  const loadTasks = useInviteStore((s) => s.loadTasks);
  const autoConnect = useSettingsStore((s) => s.settings.autoConnectOnStart);
  const loadSettings = useSettingsStore((s) => s.load);
  const healthInFlight = useRef(false);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  useEffect(() => {
    if (!autoConnect) {
      useServiceStore.setState({
        localService: "error",
        message: "已关闭自动连接，请点击连接服务",
        bootstrapped: false,
      });
      return;
    }
    void ensureBackend();
  }, [ensureBackend, autoConnect]);

  useEffect(() => {
    if (!bootstrapped) return;
    void loadConfig();
    void loadTasks();
  }, [bootstrapped, loadConfig, loadTasks]);

  useEffect(() => {
    if (localService !== "ready") return;
    const inviting = () => useInviteStore.getState().inviting;
    const tick = async () => {
      if (healthInFlight.current) return;
      healthInFlight.current = true;
      try {
        await refreshHealth();
      } finally {
        healthInFlight.current = false;
      }
    };
    const timer = window.setInterval(() => {
      void tick();
    }, inviting() ? 2000 : 5000);
    return () => window.clearInterval(timer);
  }, [localService, refreshHealth]);
}
