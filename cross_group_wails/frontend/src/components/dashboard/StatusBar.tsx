import { Settings } from "lucide-react";
import { useInviteStore } from "@/store/useInviteStore";
import { useServiceStore } from "@/store/useServiceStore";
import { useNavigationStore } from "@/store/useNavigationStore";

export function StatusBar() {
  const statusText = useInviteStore((s) => s.statusText);
  const inviting = useInviteStore((s) => s.inviting);
  const localService = useServiceStore((s) => s.localService);
  const napcatOnline = useServiceStore((s) => s.napcatOnline);
  const napcatMessage = useServiceStore((s) => s.napcatMessage);
  const navigate = useNavigationStore((s) => s.navigate);

  const serviceLabel =
    localService === "ready"
      ? "本地服务：正常"
      : localService === "port_conflict"
        ? "本地服务：端口冲突"
        : localService === "error"
          ? "本地服务：异常"
          : "本地服务：启动中";

  const napcatLabel = napcatOnline ? "饭饭定制：在线" : "饭饭定制：未连接";

  return (
    <footer className="flex h-9 shrink-0 items-center justify-between border-t border-border bg-white/90 px-4 text-[12px] text-muted-foreground">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span
            className={`h-2 w-2 rounded-full ${
              inviting ? "animate-pulse bg-primary" : localService === "ready" ? "bg-primary" : "bg-[#d49a12]"
            }`}
          />
          <span>{statusText || "就绪"}</span>
        </div>
        <span className={localService === "ready" ? "text-primary" : "text-danger"}>
          {serviceLabel}
        </span>
        <span className={napcatOnline ? "text-primary" : "text-[#d49a12]"} title={napcatMessage}>
          {napcatLabel}
        </span>
      </div>
      <button
        type="button"
        className="flex items-center gap-1 hover:text-primary"
        onClick={() => navigate("settings")}
      >
        <Settings className="h-3.5 w-3.5" />
        设置
      </button>
    </footer>
  );
}
