import { useEffect } from "react";
import { api } from "@/lib/api";
import { useServiceStore } from "@/store/useServiceStore";
import { useInviteStore } from "@/store/useInviteStore";

export function useBootstrap() {
  const ensureBackend = useServiceStore((s) => s.ensureBackend);
  const refreshHealth = useServiceStore((s) => s.refreshHealth);
  const bootstrapped = useServiceStore((s) => s.bootstrapped);
  const localService = useServiceStore((s) => s.localService);
  const loadConfig = useInviteStore((s) => s.loadConfig);

  useEffect(() => {
    void ensureBackend();
  }, [ensureBackend]);

  useEffect(() => {
    if (!bootstrapped) return;
    void loadConfig();
  }, [bootstrapped, loadConfig]);

  useEffect(() => {
    if (localService !== "ready") return;
    const timer = window.setInterval(() => {
      void refreshHealth();
      void api.health().then((h) => {
        useServiceStore.setState({
          napcatOnline: h.napcat_online,
          napcatMessage: h.napcat_message,
        });
      }).catch(() => {
        useServiceStore.setState({
          localService: "error",
          message: "��˷���δ����",
          bootstrapped: false,
        });
      });
    }, 3000);
    return () => window.clearInterval(timer);
  }, [localService, refreshHealth]);
}
