import { useEffect, useRef } from "react";
import { useInviteStore } from "@/store/useInviteStore";
import { useServiceStore } from "@/store/useServiceStore";

export function usePollingStatus() {
  const refreshStatus = useInviteStore((s) => s.refreshStatus);
  const inviting = useInviteStore((s) => s.inviting);
  const localService = useServiceStore((s) => s.localService);
  const inFlight = useRef(false);

  useEffect(() => {
    if (localService !== "ready") return;

    let cancelled = false;
    const tick = async () => {
      if (cancelled || inFlight.current) return;
      inFlight.current = true;
      try {
        await refreshStatus();
      } finally {
        inFlight.current = false;
      }
    };

    void tick();
    const timer = window.setInterval(() => {
      void tick();
    }, inviting ? 800 : 2500);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [localService, inviting, refreshStatus]);
}
