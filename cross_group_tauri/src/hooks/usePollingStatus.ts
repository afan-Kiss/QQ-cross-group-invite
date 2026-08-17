import { useEffect } from "react";
import { useInviteStore } from "@/store/useInviteStore";
import { useServiceStore } from "@/store/useServiceStore";

export function usePollingStatus(intervalMs = 1500) {
  const refreshStatus = useInviteStore((s) => s.refreshStatus);
  const inviting = useInviteStore((s) => s.inviting);
  const bootstrapped = useServiceStore((s) => s.bootstrapped);

  useEffect(() => {
    if (!bootstrapped) return;
    void refreshStatus();
  }, [bootstrapped, refreshStatus]);

  useEffect(() => {
    if (!bootstrapped) return;
    const timer = window.setInterval(() => {
      void refreshStatus();
    }, inviting ? intervalMs : intervalMs * 2);
    return () => window.clearInterval(timer);
  }, [bootstrapped, inviting, intervalMs, refreshStatus]);
}
